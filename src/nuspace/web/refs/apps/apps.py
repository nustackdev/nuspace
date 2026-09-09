"""AppsRef -- the nuspace Apps editor: a flat app rail + a Monaco canvas.

One ref owns the whole Apps surface, the same way ``PagesRef`` owns the
document surface.

- ``AppsRef``: a nu.ui Ref. Pure wire handle. Payload is stamped once in
  ``__init__`` (the ``space_root`` Shape class) and never mutated after.

- ``AppsDriver``: Control, one per connection. It ships the app list on
  boot, subscribes to this ref's wire path, dispatches each browser
  notify into substrate writes, and reships after every write it makes.

## What the driver does *not* do

It does not run anything. That is the whole structural difference from
``PagesDriver``, which owns its supervisor.

An app runs whether or not a browser is looking, so its supervisor lives
at space lifetime in the app tree (see ``runtime.py`` / ``runner.py``).
The driver looks that runtime up by root Shape class and **observes** it:
it reads current statuses on boot, subscribes to status changes for as
long as the connection lasts, and unsubscribes on teardown. Two browsers
therefore see one set of running apps rather than one set each, and a
browser that connects mid-run paints what is already running instead of
starting it.

When no runner is mounted, ``get_runtime`` returns None. That is shipped
as ``attached: false`` and rendered as such: the space is up and its
apps are simply not supervised. Inventing idle statuses would be a lie.

## Apps are headless

An app produces, a page displays. There is no display mode and no block
canvas here because an app has nothing to display: it has no ``nu.ui``
Session, it writes to kv, and a page reads that kv and renders it. So
the canvas is source plus status, and nothing else.

## Wire

Server -> browser (all ``write`` frames, dispatched on ``payload["op"]``):

    {"op": "set_apps", "apps": [App], "attached": bool}
    {"op": "set_status", "statuses": [Status]}

    App    = {"id", "name", "source", "policy", "status": Status|None}
    Status = {"section_id", "state", "error", "started_at"}

``Status.section_id`` carries the *app* id. The key name is the fixed
supervisor contract and is not renamed per pillar.

Browser -> server (``notify`` frames on one subscription):

    {"op": "on_app_create",  "name", "source"}
    {"op": "on_app_rename",  "app_id", "name"}
    {"op": "on_app_delete",  "app_id"}
    {"op": "on_app_update",  "app_id", "source"}
    {"op": "on_app_restart", "app_id"}

There is no ``on_app_select``. Selection is the URL (``/apps/<id>``), so
it is browser-owned and the server stays stateless between notifies --
same rule as Pages and Lens.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

import nu
import nu.ui
from nu.engine.structure import Declared
from nu.kv.tree import auto_flow_atomic
from nu.lang import Command, Control
from nu.ui.core import Ref, Session
from nu.ui.core.protocol import Frame
from nuspace.core.refs import mint_ordered_id

from .runtime import get_runtime


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nu.lang.runtime import Runtime


__all__ = ["AppsDriver", "AppsRef"]


MAX_APPS = 500
DEFAULT_POLICY = "always"

# Coalesce status bursts (starting -> running lands within a tick).
STATUS_FLUSH_S = 0.03

# The source a fresh app starts from. A real program, not a stub comment:
# `invalid` on a brand new app reads as nuspace being broken.


def new_app_source(root: type) -> str:
    """Starter source for a new app, addressed at *this* space's root.

    Templated rather than constant because a space may subclass ``Space``
    to add slots, and ``ShapeMeta`` rebinds ``_root_shape`` on inherited
    slots too. ``Space.state`` and ``DemoSpace.state`` are different
    addresses, and only the one matching the navigator's tag resolves --
    so a constant naming ``Space`` hands every subclassed space a new app
    that fails the moment it runs.
    """
    name = root.__name__
    return f'''import nu
from {root.__module__} import {name}


def out(path):
    """An app runs always, headless. It writes; a page reads."""
    return nu.ForeverDo(
        {name}.state.set_item(path + ".beat", nu.Str("tick")) >> nu.Delay(1.0)
    )
'''


# -- Ref ---------------------------------------------------------------------


class AppsRef(Ref):
    """Flat app list + one app's source, over a Space's ``apps`` slot.

    Configured once with a ``space_root`` Shape class whose ``.apps``
    slot is the flat ``AppsRef`` dict. The server owns the app list and
    the status; the browser owns the selection cursor (via the URL
    router) and the unsaved editor buffer.
    """

    _wire_type_override = "AppsRef"

    def __init__(
        self,
        address: object,
        *,
        parent_ref: Ref | None = None,
        owner_shape: type[Shape] | None = None,
        space_root: type[Shape] | None = None,
    ) -> None:
        super().__init__(address, parent_ref=parent_ref, owner_shape=owner_shape)
        self._payload["apps_space_root"] = space_root

    @classmethod
    def slot(cls, *, space_root: type[Shape]) -> Self:
        """Pin the ``space_root`` Shape class the driver will walk."""
        return nu.Slot(  # type: ignore[return-value]
            cls,
            props={},
            space_root=space_root,
        )

    # -- Host-side interactions (server -> browser writes) -------------------

    def set_apps(self, apps: list[dict[str, Any]], *, attached: bool = True) -> nu.Nu:
        """Ship a pre-computed app list to the browser."""
        return _AppsWrite(
            self,
            {"op": "set_apps", "apps": list(apps), "attached": bool(attached)},
        )

    def set_status(self, statuses: list[dict[str, Any]]) -> nu.Nu:
        """Ship a status batch to the browser."""
        return _AppsWrite(self, {"op": "set_status", "statuses": list(statuses)})

    # -- Subscription verb --------------------------------------------------

    def feedback(self) -> nu.Nu:
        """Subscribe to browser NOTIFY frames on this ref (one queue)."""
        return nu.ui.Changed(self)


# -- Write command -----------------------------------------------------------


class _AppsWrite(Command):
    """Ship one arbitrary payload as a wire ``write`` frame for AppsRef."""

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, ref: AppsRef, payload: dict[str, Any]) -> None:
        super().__init__(ref)
        self._payload["apps_write_payload"] = dict(payload)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("AppsRef is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: AppsRef = self._children[0]
        payload: dict[str, Any] = self._payload["apps_write_payload"]

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            await session.send(Frame("write", ref=wire_path, payload=payload))

        return athunk


# -- Driver ------------------------------------------------------------------


class AppsDriver(Control):
    """Per-connection driver: list paint, feedback dispatch, status relay."""

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: AppsRef) -> None:
        super().__init__(ref)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("AppsDriver is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: AppsRef = self._children[0]
        space_root: type[Shape] | None = ref._payload.get("apps_space_root")
        if space_root is None:
            raise RuntimeError("AppsRef.slot(space_root=...) requires a Shape class")
        root: type[Shape] = space_root

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            loop = asyncio.get_running_loop()

            # -- plumbing ----------------------------------------------------

            async def run(term: nu.Nu) -> Any:  # noqa: ANN401
                value, _ = await nu.arun(auto_flow_atomic(term, scope=root), rt.ctx)  # type: ignore[arg-type]
                return value

            async def do_write(term: nu.Nu) -> None:
                await run(term)

            async def send(payload: dict[str, Any]) -> None:
                await session.send(Frame("write", ref=wire_path, payload=payload))

            # -- status relay ------------------------------------------------
            #
            # The runtime is not ours. We attach an observer for the life of
            # this connection and detach in `finally`; supervision itself is
            # entirely unaffected by browsers coming and going.

            status_q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

            def on_status(wire: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(status_q.put_nowait, wire)

            async def status_pump() -> None:
                while True:
                    first = await status_q.get()
                    batch: dict[str, dict[str, Any]] = {first["section_id"]: first}
                    await asyncio.sleep(STATUS_FLUSH_S)
                    while not status_q.empty():
                        item = status_q.get_nowait()
                        batch[item["section_id"]] = item
                    try:
                        await send({"op": "set_status", "statuses": list(batch.values())})
                    except Exception:  # noqa: S110 -- ws gone; `finally` cleans up
                        pass

            # The runtime we are currently observing, or None. Held in a
            # cell rather than captured once because a browser can connect
            # before the runner has published, and because a restarted
            # runner publishes a *different* runtime under the same root.
            observed: dict[str, Any] = {"runtime": None}

            def observe() -> Any:  # noqa: ANN401
                """Resolve the live runtime, moving our observer if it changed."""
                live = get_runtime(root)
                if live is observed["runtime"]:
                    return live
                if observed["runtime"] is not None:
                    observed["runtime"].off_change(on_status)
                if live is not None:
                    live.on_change(on_status)
                observed["runtime"] = live
                return live

            pump = asyncio.create_task(status_pump())

            # -- shipping ----------------------------------------------------

            async def read_apps() -> list[tuple[str, dict[str, Any]]]:
                try:
                    raw = await run(root.apps.extract())
                except Exception:
                    raw = None
                if not isinstance(raw, dict):
                    return []
                items = [(str(k), v) for k, v in raw.items() if isinstance(v, dict)]
                # Ids are time-ordered, so key order is creation order --
                # the only order a flat list has, and a stable one.
                items.sort(key=lambda pair: pair[0])
                return items[:MAX_APPS]

            async def ship_apps() -> None:
                live = observe()
                apps: list[dict[str, Any]] = []
                for aid, blob in await read_apps():
                    status = live.status(aid) if live is not None else None
                    apps.append(
                        {
                            "id": aid,
                            "name": str(blob.get("name") or ""),
                            "source": str(blob.get("snippet") or ""),
                            "policy": str(blob.get("policy") or DEFAULT_POLICY),
                            "status": status,
                        },
                    )
                await send({"op": "set_apps", "apps": apps, "attached": live is not None})

            def wake() -> None:
                """Ask the supervisor to reconcile now rather than at the next poll."""
                live = observe()
                if live is not None:
                    live.wake()

            # -- dispatch ----------------------------------------------------

            async def dispatch(payload: dict[str, Any]) -> None:
                op = str(payload.get("op") or "")

                if op == "on_app_create":
                    name = str(payload.get("name") or "app")
                    source = payload.get("source")
                    await do_write(
                        root.apps.set_item(
                            mint_ordered_id("a"),
                            {
                                "name": name,
                                "snippet": new_app_source(root) if source is None else str(source),
                                "policy": DEFAULT_POLICY,
                            },
                        ),
                    )
                    wake()
                    await ship_apps()
                    return

                app_id = str(payload.get("app_id") or "")
                if not app_id:
                    return

                if op == "on_app_rename":
                    name = str(payload.get("name") or "app")
                    await do_write(root.apps[app_id].name.set(nu.Str(name)))
                    await ship_apps()
                    return

                if op == "on_app_delete":
                    await do_write(root.apps.del_item(app_id))
                    wake()
                    await ship_apps()
                    return

                if op == "on_app_update":
                    source = str(payload.get("source") or "")
                    await do_write(root.apps[app_id].snippet.set(nu.Str(source)))
                    # The supervisor diffs sources, so this restarts exactly
                    # this app and leaves every other one alone.
                    wake()
                    await ship_apps()
                    return

                if op == "on_app_restart":
                    live = observe()
                    if live is not None:
                        await live.restart(app_id)
                    return

            # -- boot --------------------------------------------------------

            await ship_apps()

            queue: asyncio.Queue[object] = asyncio.Queue()

            def on_notify(payload: object) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, payload)

            sub = session.subscribe(wire_path)
            sub.bind(on_notify)
            try:
                while True:
                    payload = await queue.get()
                    if not isinstance(payload, dict):
                        continue
                    try:
                        await dispatch(payload)
                    except Exception:  # noqa: S110 -- one bad notify must not kill the driver
                        pass
            finally:
                pump.cancel()
                if observed["runtime"] is not None:
                    observed["runtime"].off_change(on_status)
                    observed["runtime"] = None
                sub.unbind(on_notify)
                sub.close()

        return athunk
