"""FastAPI builder for a nuspace program.

Owns per-connection wiring plus a small control plane:

- ``GET /`` and static assets: serve the ``nuspace_ui`` SPA if present.
- ``WS /ws``: mount + run per-connection body.
- ``POST /control/primitive``: external processes (the cli) invoke named
  primitives here; the server runs them under its Nu runtime (the only
  process holding the rocksdb lock), then rebuilds MOUNT + body on every
  connected session.

The rebuild-on-primitive path is a v0 compromise: state changes drive UI
via a python-level coordinator rather than a Nu ``ReactForever`` wire on
``pages_index``/``blocks``/``active_page``. Good enough to see e2e now;
Model B purity comes later.
"""

from __future__ import annotations

import asyncio
import warnings
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from nu.lang.helpers import arun
from nu.ui.core import Session

from .session import NuspaceSession


if TYPE_CHECKING:
    from nu.lang import Context, Nu


__all__ = ["build_fastapi_app"]


MountFactory = Callable[["Context"], Awaitable[dict]]
BodyFactory = Callable[["Context"], Awaitable["Nu"]]
PrimitiveDispatch = Callable[[str, dict], Awaitable[None]]


class _Conn:
    """One live ws connection: session, its bound ctx, and its body task."""

    def __init__(self, session: NuspaceSession, ctx: Context) -> None:
        self.session = session
        self.ctx = ctx
        self.body_task: asyncio.Task | None = None
        self.stopped = False


def _bundled_static() -> Path | None:
    try:
        import nuspace_ui
    except ImportError:
        return None
    if not hasattr(nuspace_ui, "__path__"):
        warnings.warn(
            f"`import nuspace_ui` resolved to {nuspace_ui.__file__!r} (a module, "
            "not the ui wheel package). SPA mount skipped; only /ws is exposed.",
            stacklevel=2,
        )
        return None
    paths = list(nuspace_ui.__path__)
    if not paths:
        return None
    build = Path(paths[0]) / "build"
    if not (build / "index.html").exists():
        return None
    return build


class _SPAStatic(StaticFiles):
    async def get_response(self, path: str, scope: object) -> object:
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as e:
            if e.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if getattr(response, "status_code", 200) == 404:
            return await super().get_response("index.html", scope)
        return response


def build_fastapi_app(
    ctx: Context,
    get_mount_payload: MountFactory,
    get_body: BodyFactory,
    build_primitive: Callable[[str, dict], "Nu"],
) -> FastAPI:
    """Build the FastAPI app.

    ``ctx``: base ctx with the rocksdb navigator bound; primitives run here.
    ``get_mount_payload(ctx)``: called per rebuild to compute the MOUNT payload.
    ``get_body(ctx)``: called per rebuild to construct the per-connection Nu body.
    ``build_primitive(op, args)``: named primitive -> Nu term (for /control).
    """
    fastapi_app = FastAPI(title="nuspace")
    conns: set[_Conn] = set()
    conns_lock = asyncio.Lock()

    async def _spawn_body(conn: _Conn) -> None:
        try:
            body = await get_body(conn.ctx)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"nuspace: build body failed: {exc}", stacklevel=2)
            return
        if body is None:
            return
        conn.body_task = asyncio.create_task(arun(body, conn.ctx))

    async def _cancel_body(conn: _Conn) -> None:
        task = conn.body_task
        conn.body_task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass

    async def _refresh_conn(conn: _Conn) -> None:
        if conn.stopped:
            return
        try:
            payload = await get_mount_payload(conn.ctx)
            await conn.session.mount(payload)
        except Exception as exc:  # noqa: BLE001
            warnings.warn(f"nuspace: mount push failed: {exc}", stacklevel=2)
            return
        await _cancel_body(conn)
        await _spawn_body(conn)

    async def _broadcast_refresh() -> None:
        async with conns_lock:
            targets = list(conns)
        await asyncio.gather(*(_refresh_conn(c) for c in targets), return_exceptions=True)

    @fastapi_app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        session = NuspaceSession(ws)
        per_conn_ctx = ctx.bind(Session, session)
        conn = _Conn(session, per_conn_ctx)
        async with conns_lock:
            conns.add(conn)
        try:
            payload = await get_mount_payload(per_conn_ctx)
            await session.mount(payload)
            await _spawn_body(conn)
            intake_task = asyncio.create_task(session.run_intake())
            try:
                await intake_task
            finally:
                await _cancel_body(conn)
        finally:
            conn.stopped = True
            async with conns_lock:
                conns.discard(conn)

    @fastapi_app.post("/control/primitive")
    async def control_primitive(body: dict) -> dict:
        op = body.get("op")
        args = body.get("args") or {}
        if not isinstance(op, str):
            raise HTTPException(status_code=400, detail="op must be a string")
        try:
            term = build_primitive(op, args)
        except (KeyError, ValueError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        try:
            import nu

            await arun(nu.kv.Transaction(term), ctx)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=500, detail=f"primitive failed: {exc}") from exc
        await _broadcast_refresh()
        return {"ok": True}

    @fastapi_app.get("/control/state")
    async def control_state() -> dict:
        """Read-only snapshot of the pages listing (used by cli `ls`)."""
        payload = await get_mount_payload(ctx)
        return payload

    static_dir = _bundled_static()
    if static_dir is not None and static_dir.exists():
        fastapi_app.mount(
            "/",
            _SPAStatic(directory=static_dir, html=True),
            name="static",
        )
    return fastapi_app
