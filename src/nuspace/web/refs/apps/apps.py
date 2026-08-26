"""AppsRef -- nested folder tree + code editor over ``Space.apps``.

Two moving parts, mirroring the ``LensRef`` pattern.

- ``AppsRef``: a nu.ui Ref. Pure wire handle. Payload is stamped once in
  ``__init__`` (the ``space_root`` Shape class) and never mutated after.
  All runtime state lives in the browser slice; the server is stateless
  between notifies. The ref exposes two host-driven Write commands
  (``set_tree``, ``set_app``) plus a subscription verb (``feedback()``)
  so drivers can react to browser events.

- ``AppsShipTree``: Command. Reads ``Space.apps.extract()``, folds the
  result into the browser tree payload, ships one ``set_tree`` write.
  Reusable when external code wants to nudge the browser after a
  non-driver mutation (compose as a ``ReactForever`` body once nu's
  reactive subscription for arbitrary-depth wildcards lands).

- ``AppsFeedbackDriver``: Control. Ships the current tree on mount,
  subscribes to this ref's wire path, dispatches each browser notify
  (one op per notify) into substrate writes, and explicitly re-ships
  the tree after every write it makes so the browser stays in sync.

Server-owned wire payloads (msgpack-native):

    write:  {"op": "set_tree", "tree": {...}}
    write:  {"op": "set_app",  "app_id": str, "name": str, "code": str}

Browser feedback (client -> server, all as ``notify`` frames):

    {"op": "app_select", "path": [gid..., aid]}
    {"op": "app_edit",   "path": [gid..., aid], "name": str, "code": str}
    {"op": "app_create", "group_path": [gid...], "name": str}
    {"op": "app_rename", "path": [gid..., aid], "name": str}
    {"op": "app_delete", "path": [gid..., aid]}
    {"op": "group_create", "parent_path": [gid...], "name": str}
    {"op": "group_rename", "path": [gid...], "name": str}
    {"op": "group_delete", "path": [gid...]}

Tree payload shape (server -> browser, msgpack-native, no Nu Refs):

    {
      "groups": [
        {"id": "g_...", "name": "ops",
         "groups": [...], "apps": [{"id": "a_...", "name": "cron"}, ...]},
        ...
      ],
      "apps": [{"id": "a_...", "name": "hello"}, ...]
    }
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

import nu
from nu.engine.structure import Declared
from nu.kv.tree import auto_flow_atomic
from nu.lang import Command, Control
from nu.ui.core import Ref, Session
from nu.ui.core.protocol import Frame


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nu.domains.shape import Shape
    from nu.lang.runtime import Runtime


__all__ = ["AppsFeedbackDriver", "AppsRef", "AppsShipTree"]


# -- Ref ---------------------------------------------------------------------


class AppsRef(Ref):
    """Nested apps tree + code editor over a Space's app root.

    Configured once with a ``space_root`` Shape class whose ``.apps``
    slot is a ``ShapeRef`` to the top ``Group``. The server owns the
    tree/app payloads; the browser owns the selection cursor, the
    editor buffer, and the expanded-groups set.
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
        # No runtime state ever added to payload; mutating it after
        # construction would bleed across Nu tree rewrites that share
        # the same payload reference.

    @classmethod
    def slot(cls, *, space_root: type[Shape]) -> Self:
        """Pin the ``space_root`` Shape class the driver will walk."""
        return nu.Slot(  # type: ignore[return-value]
            cls,
            props={},
            space_root=space_root,
        )

    # -- Host-side interactions (server -> browser writes) -------------------

    def set_tree(self, tree: dict[str, Any]) -> nu.Nu:
        """Ship a pre-computed tree payload to the browser."""
        return _AppsWrite(self, {"op": "set_tree", "tree": tree})

    def set_app(self, app_id: str, name: str, code: str) -> nu.Nu:
        """Ship a single app's editable payload to the browser."""
        return _AppsWrite(
            self,
            {"op": "set_app", "app_id": str(app_id), "name": str(name), "code": str(code)},
        )

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


# -- Tree helpers ------------------------------------------------------------


def _build_tree_from_extract(root_data: dict[str, Any] | None) -> dict[str, Any]:
    """Turn ``Space.apps.extract()`` into the browser-facing tree payload."""
    if not isinstance(root_data, dict):
        return {"groups": [], "apps": []}
    return _group_body(root_data)


def _group_body(data: dict[str, Any]) -> dict[str, Any]:
    apps_raw = data.get("apps") or {}
    groups_raw = data.get("groups") or {}
    apps_list = []
    if isinstance(apps_raw, dict):
        for aid, app in sorted(apps_raw.items()):
            if not isinstance(app, dict):
                continue
            apps_list.append({"id": str(aid), "name": str(app.get("name") or aid)})
    groups_list = []
    if isinstance(groups_raw, dict):
        for gid, group in sorted(groups_raw.items()):
            if not isinstance(group, dict):
                continue
            body = _group_body(group)
            body["id"] = str(gid)
            body["name"] = str(group.get("name") or gid)
            groups_list.append(body)
    return {"groups": groups_list, "apps": apps_list}


def _walk_to_apps(space_root: type[Shape], group_path: list[str]) -> object:
    """Return the ``AppsRef`` at ``group_path`` (empty = top group)."""
    ref = space_root.apps
    for gid in group_path:
        ref = ref.groups[gid]
    return ref.apps


def _walk_to_group(space_root: type[Shape], group_path: list[str]) -> object:
    """Return the ``GroupsRef`` container at ``group_path``."""
    ref = space_root.apps
    for gid in group_path:
        ref = ref.groups[gid]
    return ref.groups


def _walk_app(
    space_root: type[Shape],
    path: list[str],
) -> tuple[object, list[str], str]:
    """Split ``[gid..., aid]`` into (parent AppsRef, group_path, app_id)."""
    if not path:
        raise ValueError("app path is empty")
    aid = str(path[-1])
    group_path = [str(s) for s in path[:-1]]
    return _walk_to_apps(space_root, group_path), group_path, aid


def _walk_group(
    space_root: type[Shape],
    path: list[str],
) -> tuple[object, list[str], str]:
    """Split ``[gid..., gid]`` into (parent GroupsRef, parent_path, group_id)."""
    if not path:
        raise ValueError("group path is empty")
    gid = str(path[-1])
    parent_path = [str(s) for s in path[:-1]]
    return _walk_to_group(space_root, parent_path), parent_path, gid


# -- Ship-tree command (used from ReactForever bodies + at boot) ------------


class AppsShipTree(Command):
    """Extract Space.apps and ship one ``set_tree`` write frame.

    Reads ``space_root`` off the ref's payload -- same source of truth
    as the driver. Runs on every substrate change under ``Space.apps``
    when composed as the body of a ``ReactForever`` in the app tree,
    and once at boot from the driver's initial paint step (so the
    browser doesn't wait for a change to see anything).
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, ref: AppsRef) -> None:
        super().__init__(ref)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("AppsRef is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: AppsRef = self._children[0]
        space_root: type[Shape] | None = ref._payload.get("apps_space_root")
        if space_root is None:
            raise RuntimeError("AppsRef.slot(space_root=...) requires a Shape class")

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            extract_term = auto_flow_atomic(space_root.apps.extract(), scope=space_root)
            data, _ = await nu.arun(extract_term, rt.ctx)  # type: ignore[arg-type]
            tree = _build_tree_from_extract(data if isinstance(data, dict) else None)
            await session.send(
                Frame("write", ref=wire_path, payload={"op": "set_tree", "tree": tree}),
            )

        return athunk


# -- Driver: browser feedback dispatch --------------------------------------


class AppsFeedbackDriver(Control):
    """Per-connection driver: initial tree paint + feedback dispatch.

    On boot: ships the current tree once so the browser has something
    to show. Then loops on browser notifies, switching on ``payload["op"]``
    into substrate writes. After every mutating handler the driver
    re-ships the tree so the browser stays in sync. Reads/writes stay
    inside ``auto_flow_atomic(scope=space_root)`` so the substrate is
    reachable regardless of how the driver was composed into the app tree.

    Runs forever inside the app tree. No ref-side runtime state.
    """

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: AppsRef) -> None:
        super().__init__(ref)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("AppsFeedbackDriver is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: AppsRef = self._children[0]
        space_root: type[Shape] | None = ref._payload.get("apps_space_root")
        if space_root is None:
            raise RuntimeError("AppsRef.slot(space_root=...) requires a Shape class")

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)

            async def ship_tree_now() -> None:
                extract_term = auto_flow_atomic(
                    space_root.apps.extract(),
                    scope=space_root,
                )
                data, _ = await nu.arun(extract_term, rt.ctx)  # type: ignore[arg-type]
                tree = _build_tree_from_extract(data if isinstance(data, dict) else None)
                await session.send(
                    Frame(
                        "write",
                        ref=wire_path,
                        payload={"op": "set_tree", "tree": tree},
                    ),
                )

            async def ship_app(path: list[str]) -> None:
                if not path:
                    return
                apps_ref, _gp, aid = _walk_app(space_root, path)
                # extract() materialises the whole App subtree in one
                # call; get_item() on a ShapesDict returns a lazy view
                # that isn't a dict yet in this codepath.
                get_term = auto_flow_atomic(apps_ref[aid].extract(), scope=space_root)
                try:
                    raw, _ = await nu.arun(get_term, rt.ctx)  # type: ignore[arg-type]
                except Exception:
                    raw = None
                if not isinstance(raw, dict):
                    raw = {}
                await session.send(
                    Frame(
                        "write",
                        ref=wire_path,
                        payload={
                            "op": "set_app",
                            "app_id": str(aid),
                            "name": str(raw.get("name") or aid),
                            "code": str(raw.get("snippet") or ""),
                        },
                    ),
                )

            async def do_write(term: nu.Nu) -> None:
                await nu.arun(auto_flow_atomic(term, scope=space_root), rt.ctx)

            # Initial paint so a fresh connection sees the tree without
            # waiting for a change.
            await ship_tree_now()

            loop = asyncio.get_running_loop()
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
                        await _dispatch(
                            payload,
                            space_root=space_root,
                            rt=rt,
                            ship_app=ship_app,
                            ship_tree=ship_tree_now,
                            do_write=do_write,
                        )
                    except Exception:  # noqa: S110 -- one bad notify shouldn't die
                        pass
            finally:
                sub.unbind(on_notify)
                sub.close()

        return athunk


async def _dispatch(
    payload: dict[str, Any],
    *,
    space_root: type[Shape],
    rt: Runtime,
    ship_app: Callable[[list[str]], Awaitable[None]],
    ship_tree: Callable[[], Awaitable[None]],
    do_write: Callable[[nu.Nu], Awaitable[None]],
) -> None:
    op = str(payload.get("op") or "")
    tree_dirty = False
    if op == "app_select":
        await ship_app(_as_str_list(payload.get("path")))
    elif op == "app_edit":
        path = _as_str_list(payload.get("path"))
        if not path:
            return
        apps_ref, _gp, aid = _walk_app(space_root, path)
        name = str(payload.get("name") or aid)
        code = str(payload.get("code") or "")
        await do_write(
            apps_ref.set_item(
                aid,
                {"name": name, "snippet": code, "policy": "always"},
            ),
        )
        await ship_app(path)
        tree_dirty = True
    elif op == "app_create":
        group_path = _as_str_list(payload.get("group_path"))
        name = str(payload.get("name") or "app")
        apps_ref = _walk_to_apps(space_root, group_path)
        await do_write(apps_ref.add(name=name))
        tree_dirty = True
    elif op == "app_rename":
        path = _as_str_list(payload.get("path"))
        if not path:
            return
        apps_ref, _gp, aid = _walk_app(space_root, path)
        get_term = auto_flow_atomic(apps_ref[aid].extract(), scope=space_root)
        cur, _ = await nu.arun(get_term, rt.ctx)  # type: ignore[arg-type]
        if not isinstance(cur, dict):
            cur = {}
        cur = dict(cur)
        cur["name"] = str(payload.get("name") or aid)
        await do_write(apps_ref.set_item(aid, cur))
        tree_dirty = True
    elif op == "app_delete":
        path = _as_str_list(payload.get("path"))
        if not path:
            return
        apps_ref, _gp, aid = _walk_app(space_root, path)
        await do_write(apps_ref.del_item(aid))
        tree_dirty = True
    elif op == "group_create":
        parent_path = _as_str_list(payload.get("parent_path"))
        name = str(payload.get("name") or "group")
        groups_ref = _walk_to_group(space_root, parent_path)
        await do_write(groups_ref.add(name=name))
        tree_dirty = True
    elif op == "group_rename":
        path = _as_str_list(payload.get("path"))
        if not path:
            return
        groups_ref, _pp, gid = _walk_group(space_root, path)
        get_term = auto_flow_atomic(groups_ref[gid].extract(), scope=space_root)
        cur, _ = await nu.arun(get_term, rt.ctx)  # type: ignore[arg-type]
        if not isinstance(cur, dict):
            cur = {}
        cur = dict(cur)
        cur["name"] = str(payload.get("name") or gid)
        await do_write(groups_ref.set_item(gid, cur))
        tree_dirty = True
    elif op == "group_delete":
        path = _as_str_list(payload.get("path"))
        if not path:
            return
        groups_ref, _pp, gid = _walk_group(space_root, path)
        await do_write(groups_ref.del_item(gid))
        tree_dirty = True
    if tree_dirty:
        await ship_tree()


def _as_str_list(raw: object) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(s) for s in raw]
