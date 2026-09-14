"""FastAPI app builder for a nuspace Nu program, and the ``/ws`` endpoint.

Not a Nu. A plain builder that takes a nuspace Nu program + Shell class +
Context and returns a ``FastAPI`` instance with ``/ws`` wired up: each
connection gets a fresh ``NuspaceSession`` bound on ctx, and the user's
Nu evaluates in parallel with ``session.run_intake`` draining inbound
frames.

Called from ``NuspaceServer.asetup`` -- the bracket owns the uvicorn
lifecycle.
"""

from __future__ import annotations

import asyncio
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import nu
from nu.lang.helpers import arun
from nu.ui.core import Session
from nuspace.core.host import free_port
from nuspace.core.session import HostedSession, served_session

from .session import NuspaceSession
from .shell import Shell


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Context, Nu


__all__ = ["build_fastapi_app"]


def _bundled_static() -> Path | None:
    """Resolve the compiled web bundle shipped by the ``nuspace_ui`` wheel.

    Returns None when the wheel is not installed -- the backend still
    boots (headless / dev / tests); the browser mount is just skipped.
    """
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
    # nuspace_ui is a namespace-style package (no __init__.py -- the wheel
    # only ships the build/ tree under force-include). Use __path__ directly.
    pkg_root = Path(next(iter(nuspace_ui.__path__)))
    build = pkg_root / "build"
    if not (build / "index.html").exists():
        return None
    return build


class _SPAStatic(StaticFiles):
    """StaticFiles that falls back to index.html on 404 for SPA routing."""

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
    app: Nu | Callable[[str], Nu], ctx: Context, *, shell_cls: type[Shell]
) -> FastAPI:
    """Build the FastAPI app for a nuspace program.

    ``app`` may be a callable returning a Nu, in which case it is called once
    per connection with the address this connection's Session is served at. A
    view's driver holds that connection's subscriptions, so a surface whose
    route is per view is built here rather than at the top, and anything that
    dispatches work to another process needs that address as a literal.

    Static assets come from the sibling ``nuspace_ui`` wheel (packaged
    vite build under ``nuspace_ui/build/``). If the wheel is not
    installed (or its build/ is empty), the static mount is skipped and
    only ``/ws`` is exposed -- run vite separately in that case.
    """
    if not (isinstance(shell_cls, type) and issubclass(shell_cls, Shell)):
        raise TypeError(
            f"shell_cls must be a nuspace Shell subclass, got {shell_cls!r}",
        )
    # Walked once, here: the shell is a class and its slots do not move, so
    # every connection is sent the same batch.
    chains = shell_cls._boot_chains()
    fastapi_app = FastAPI(title="nuspace")

    @fastapi_app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        session = NuspaceSession(ws)
        await session.boot(chains)
        # This connection's Session, on a socket of its own, so the pool
        # workers running its sections can write through it. The bracket
        # closes with the body, which is what ties the server to the tab.
        address = f"127.0.0.1:{free_port()}"
        per_conn_ctx = ctx.bind(Session, session).bind(HostedSession, HostedSession(session))
        inner = app(address) if callable(app) else app
        body = nu.With(served_session(address), body=inner)
        intake_task = asyncio.create_task(session.run_intake())
        eval_task = asyncio.create_task(arun(body, per_conn_ctx))
        try:
            done, _ = await asyncio.wait(
                {intake_task, eval_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in done:
                exc = t.exception()
                if exc is not None and not isinstance(exc, asyncio.CancelledError):
                    raise exc
        finally:
            for t in (intake_task, eval_task):
                if not t.done():
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):  # noqa: S110
                        pass

    static_dir = _bundled_static()
    if static_dir is not None and static_dir.exists():
        fastapi_app.mount(
            "/",
            _SPAStatic(directory=static_dir, html=True),
            name="static",
        )
    return fastapi_app
