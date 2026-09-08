"""PagesRef -- the nuspace Pages editor: page tree + block canvas.

One ref owns the whole Pages surface.

- ``PagesRef``: a nu.ui Ref. Pure wire handle. Payload is stamped once in
  ``__init__`` (the ``space_root`` Shape class) and never mutated after.
  All runtime state lives in the browser slice or in the driver's
  per-connection closure -- mutating ``_payload`` after construction
  bleeds across Nu tree rewrites that share the payload reference.

- ``PagesDriver``: Control, one per connection. Ships the page tree on
  boot, subscribes to this ref's wire path, dispatches each browser
  notify into substrate writes, and re-ships explicitly after every write
  it makes (nu has no deep-wildcard reactive subscription, so the driver
  owns invalidation).

The driver does not run sections itself. It owns a ``SectionSupervisor``
(see ``supervise.py``) and reconciles it against the open page. In v1
that is ``LocalSupervisor``; task-139's out-of-process executor drops in
behind the same five methods.

## Blocks

A page is an ordered list of blocks. Each block is a ``Section`` in kv
and carries a ``kind``:

- ``prose``   -- one prose island. ``source`` is markdown. Contiguous
  prose is *one* block, not one per paragraph; splitting is explicit.
  Never compiled, never runs, no status.
- ``program`` -- a Nu program. ``source`` is Python evaluated with
  ``{nu, Space, path}``; ``path`` is ``"sections.<block_id>"``.

Order comes from the ``order`` int slot, ties broken by id. The driver
renormalizes orders to ``index * 10`` after any structural change, so
gaps never close.

**Path is the mounting mechanism.** Every ui ref a program block names
under its own prefix mounts in that block. A block may name another
block's ref to read or write it -- a live cross-block wire that keeps
working -- but a borrowed ref renders once, in its owner. See
``compile.enumerate_ui_refs``.

There is no page-global code/display mode. v0 had one and it meant
editing anything restarted everything. Mode is per block and lives in the
browser; the server only ever hears about a *save*.

## Wire

Server -> browser (all ``write`` frames, dispatched on ``payload["op"]``):

    {"op": "set_tree", "tree": PageNode}
    {"op": "set_page", "page_id": str|None, "path": [str], "title": str,
                       "blocks": [Block]}
    {"op": "set_status", "statuses": [Status]}

    PageNode = {"id": str|None, "title": str, "pages": [PageNode]}
    Block    = {"id", "kind": "prose"|"program", "source", "order": int,
                "fields": [MountField], "status": Status|None}
    Status   = {"section_id", "state", "error", "started_at"}

Browser -> server (``notify`` frames on one subscription):

    {"op": "on_page_select",  "path": [pid...]}
    {"op": "on_page_create",  "parent_path": [pid...], "title"}
    {"op": "on_page_rename",  "path": [pid...], "title"}
    {"op": "on_page_delete",  "path": [pid...]}
    {"op": "on_block_create", "page_path", "kind", "source", "after": id|None}
    {"op": "on_block_update", "page_path", "block_id", "source"}
    {"op": "on_block_delete", "page_path", "block_ids": [id...]}
    {"op": "on_block_split",  "page_path", "block_id", "head", "tail",
                              "insert": {"kind","source"}|None}
    {"op": "on_block_merge",  "page_path", "block_id", "into_id", "source"}
    {"op": "on_block_reorder","page_path", "order": [id...]}
    {"op": "on_block_restart","page_path", "block_id"}
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
from nuspace.web.refs.pages.supervise import LocalSupervisor, SectionSpec


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nu.lang.runtime import Runtime


__all__ = ["PagesDriver", "PagesRef"]


MAX_CHILD_PAGES = 200
MAX_PAGE_DEPTH = 12
MAX_BLOCKS = 300
ORDER_STEP = 10

KIND_PROSE = "prose"
KIND_PROGRAM = "program"
KINDS = (KIND_PROSE, KIND_PROGRAM)

# Coalesce status bursts (starting -> running lands within a tick).
STATUS_FLUSH_S = 0.03


# -- Ref ---------------------------------------------------------------------


class PagesRef(Ref):
    """Nested page tree + per-page block canvas over a Space's page root.

    Configured once with a ``space_root`` Shape class whose ``.pages``
    slot is a ``ShapeRef`` to the root ``Page``. The server owns the tree,
    the active page payload, and section status; the browser owns the
    selection cursor (via the URL router), per-block edit mode, caret,
    selection, and unsaved buffers.
    """

    _wire_type_override = "PagesRef"

    def __init__(
        self,
        address: object,
        *,
        parent_ref: Ref | None = None,
        owner_shape: type[Shape] | None = None,
        space_root: type[Shape] | None = None,
    ) -> None:
        super().__init__(address, parent_ref=parent_ref, owner_shape=owner_shape)
        self._payload["pages_space_root"] = space_root

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
        """Ship a pre-computed page-tree payload to the browser."""
        return _PagesWrite(self, {"op": "set_tree", "tree": tree})

    def set_page(self, page: dict[str, Any]) -> nu.Nu:
        """Ship a pre-computed active-page payload to the browser."""
        return _PagesWrite(self, {"op": "set_page", **dict(page)})

    # -- Subscription verb --------------------------------------------------

    def feedback(self) -> nu.Nu:
        """Subscribe to browser NOTIFY frames on this ref (one queue)."""
        return nu.ui.Changed(self)


# -- Write command -----------------------------------------------------------


class _PagesWrite(Command):
    """Ship one arbitrary payload as a wire ``write`` frame for PagesRef."""

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, ref: PagesRef, payload: dict[str, Any]) -> None:
        super().__init__(ref)
        self._payload["pages_write_payload"] = dict(payload)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("PagesRef is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: PagesRef = self._children[0]
        payload: dict[str, Any] = self._payload["pages_write_payload"]

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            await session.send(Frame("write", ref=wire_path, payload=payload))

        return athunk


# -- Substrate walking -------------------------------------------------------


def _page_ref(space_root: type[Shape], path: list[str]) -> Any:  # noqa: ANN401
    """Return the ``PageRef`` at ``path``; empty path = the root page."""
    ref = space_root.pages
    for pid in path:
        ref = ref.pages[str(pid)]
    return ref


def _parent_pages(space_root: type[Shape], path: list[str]) -> tuple[Any, str]:
    """Split ``[pid..., pid]`` into (parent pages container, page_id)."""
    if not path:
        raise ValueError("page path is empty; the root page has no parent")
    return _page_ref(space_root, path[:-1]).pages, str(path[-1])


def _page_node(data: object, pid: str | None, depth: int) -> dict[str, Any]:
    """One rail node from an ``extract()`` blob. Blocks are not shown."""
    if not isinstance(data, dict):
        return {"id": pid, "title": str(pid or ""), "pages": []}
    kids_raw = data.get("pages")
    kids: list[dict[str, Any]] = []
    if isinstance(kids_raw, dict) and depth < MAX_PAGE_DEPTH:
        for kid, blob in sorted(kids_raw.items())[:MAX_CHILD_PAGES]:
            kids.append(_page_node(blob, str(kid), depth + 1))
    return {"id": pid, "title": str(data.get("title") or (pid or "")), "pages": kids}


def _ordered_blocks(raw: object) -> list[tuple[str, dict[str, Any]]]:
    """Sort a sections ``extract()`` blob by ``order`` then id.

    ``order`` may be missing (pre-``order`` stores, or a set_item that
    skipped it) or read back as a Nu sentinel rather than an int. Both
    fall back to id order, which is creation order because
    ``mint_ordered_id`` is time-prefixed.
    """
    if not isinstance(raw, dict):
        return []
    items: list[tuple[str, dict[str, Any]]] = []
    for sid, blob in raw.items():
        if isinstance(blob, dict):
            items.append((str(sid), blob))

    def key(pair: tuple[str, dict[str, Any]]) -> tuple[int, str]:
        order = pair[1].get("order")
        return (int(order) if isinstance(order, int) else 1 << 30, pair[0])

    items.sort(key=key)
    return items


def _kind_of(blob: dict[str, Any]) -> str:
    kind = blob.get("kind")
    return kind if kind in KINDS else KIND_PROGRAM


# -- Driver ------------------------------------------------------------------


class PagesDriver(Control):
    """Per-connection driver: tree paint, feedback dispatch, supervision.

    Active page path is loop-local closure state, never ref payload -- it
    dies with the connection, exactly like ``LensDriver``'s cursor.
    Reload restarts from whatever the browser's URL says.
    """

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: PagesRef) -> None:
        super().__init__(ref)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("PagesDriver is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: PagesRef = self._children[0]
        space_root: type[Shape] | None = ref._payload.get("pages_space_root")
        if space_root is None:
            raise RuntimeError("PagesRef.slot(space_root=...) requires a Shape class")
        root: type[Shape] = space_root

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)

            cursor: dict[str, Any] = {"path": []}
            supervisor = LocalSupervisor(rt.ctx, root)
            loop = asyncio.get_running_loop()

            # -- plumbing ----------------------------------------------------

            async def run(term: nu.Nu) -> Any:  # noqa: ANN401
                value, _ = await nu.arun(auto_flow_atomic(term, scope=root), rt.ctx)  # type: ignore[arg-type]
                return value

            async def do_write(term: nu.Nu) -> None:
                await run(term)

            async def send(payload: dict[str, Any]) -> None:
                await session.send(Frame("write", ref=wire_path, payload=payload))

            # -- status pump -------------------------------------------------
            #
            # Supervision emits from whatever task the section runs on. We
            # funnel into one queue and coalesce, so a burst of
            # starting/running transitions is one frame, not five.

            status_q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

            def on_status(wire: dict[str, Any]) -> None:
                loop.call_soon_threadsafe(status_q.put_nowait, wire)

            supervisor.on_change(on_status)

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
                    except Exception:  # noqa: S110 -- ws gone; the driver's finally cleans up
                        pass

            pump = asyncio.create_task(status_pump())

            # -- shipping ----------------------------------------------------

            async def ship_tree() -> None:
                try:
                    data = await run(root.pages.extract())
                except Exception:
                    data = None
                tree = _page_node(data if isinstance(data, dict) else {}, None, 0)
                await send({"op": "set_tree", "tree": tree})

            async def read_blocks(path: list[str]) -> list[tuple[str, dict[str, Any]]]:
                page = _page_ref(root, path)
                try:
                    raw = await run(page.sections.extract())
                except Exception:
                    raw = None
                return _ordered_blocks(raw)[:MAX_BLOCKS]

            async def ship_page(path: list[str]) -> None:
                page = _page_ref(root, path)
                try:
                    raw_title = await run(page.title)
                except Exception:
                    raw_title = None
                # An unset StrRef reads back as a Nu sentinel, not "".
                title = raw_title if isinstance(raw_title, str) else ""

                items = await read_blocks(path)

                # Reconcile supervision to this page's program blocks
                # *before* shipping, so the payload carries live fields
                # and live status. Nothing is started yet.
                specs = [
                    SectionSpec(sid, str(blob.get("snippet") or ""))
                    for sid, blob in items
                    if _kind_of(blob) == KIND_PROGRAM
                ]
                supervisor.plan(specs)

                blocks: list[dict[str, Any]] = []
                for index, (sid, blob) in enumerate(items):
                    kind = _kind_of(blob)
                    order = blob.get("order")
                    entry: dict[str, Any] = {
                        "id": sid,
                        "kind": kind,
                        "source": str(blob.get("snippet") or ""),
                        "order": int(order) if isinstance(order, int) else index * ORDER_STEP,
                        "fields": [],
                        "status": None,
                    }
                    if kind == KIND_PROGRAM:
                        entry["fields"] = supervisor.fields(sid)
                        entry["status"] = supervisor.status(sid)
                    blocks.append(entry)

                # Ship first so the browser has the field slices registered
                # before a running section writes to them. ws frames are
                # ordered, so this is enough.
                await send(
                    {
                        "op": "set_page",
                        "page_id": str(path[-1]) if path else None,
                        "path": list(path),
                        "title": title,
                        "blocks": blocks,
                    },
                )
                await supervisor.launch()

            async def reship_page() -> None:
                await ship_page(list(cursor["path"]))

            # -- structural writes -------------------------------------------

            async def renumber(path: list[str], ordered_ids: list[str]) -> None:
                """Rewrite every block's ``order`` to ``index * ORDER_STEP``."""
                sections = _page_ref(root, path).sections
                for index, sid in enumerate(ordered_ids):
                    await do_write(sections[sid].order.set(nu.Int(index * ORDER_STEP)))

            async def create_block(
                path: list[str],
                kind: str,
                source: str,
                after: str | None,
            ) -> str:
                sections = _page_ref(root, path).sections
                new_id = mint_ordered_id("s")
                await do_write(
                    sections.set_item(
                        new_id,
                        {
                            "name": kind,
                            "snippet": source,
                            "kind": kind if kind in KINDS else KIND_PROSE,
                            "order": 0,
                            "policy": "on_navigate",
                        },
                    ),
                )
                ids = [sid for sid, _ in await read_blocks(path) if sid != new_id]
                if after is None or after not in ids:
                    ids.append(new_id)
                else:
                    ids.insert(ids.index(after) + 1, new_id)
                await renumber(path, ids)
                return new_id

            async def update_source(path: list[str], block_id: str, source: str) -> None:
                sections = _page_ref(root, path).sections
                await do_write(sections[block_id].snippet.set(nu.Str(source)))

            async def delete_blocks(path: list[str], block_ids: list[str]) -> None:
                sections = _page_ref(root, path).sections
                for bid in block_ids:
                    await do_write(sections.del_item(bid))
                await renumber(path, [sid for sid, _ in await read_blocks(path)])

            # -- dispatch ----------------------------------------------------

            async def dispatch(payload: dict[str, Any]) -> None:
                op = str(payload.get("op") or "")

                if op == "on_page_select":
                    path = _as_str_list(payload.get("path"))
                    if path == list(cursor["path"]):
                        return
                    cursor["path"] = path
                    await supervisor.stop_all()
                    await ship_page(path)
                    return

                if op == "on_page_create":
                    parent = _as_str_list(payload.get("parent_path"))
                    title = str(payload.get("title") or "page")
                    container = _page_ref(root, parent).pages
                    await do_write(
                        container.set_item(
                            mint_ordered_id("p"),
                            {"title": title, "sections": {}, "pages": {}},
                        ),
                    )
                    await ship_tree()
                    return

                if op == "on_page_rename":
                    path = _as_str_list(payload.get("path"))
                    title = str(payload.get("title") or "page")
                    await do_write(_page_ref(root, path).title.set(nu.Str(title)))
                    await ship_tree()
                    return

                if op == "on_page_delete":
                    path = _as_str_list(payload.get("path"))
                    if not path:
                        return  # the root page is structural
                    container, pid = _parent_pages(root, path)
                    await do_write(container.del_item(pid))
                    await ship_tree()
                    if list(cursor["path"])[: len(path)] == path:
                        cursor["path"] = path[:-1]
                        await supervisor.stop_all()
                        await reship_page()
                    return

                page_path = _as_str_list(payload.get("page_path"))

                if op == "on_block_create":
                    kind = str(payload.get("kind") or KIND_PROSE)
                    source = str(payload.get("source") or "")
                    after = payload.get("after")
                    await create_block(page_path, kind, source, str(after) if after else None)
                    await reship_page()
                    return

                if op == "on_block_update":
                    bid = str(payload.get("block_id") or "")
                    if not bid:
                        return
                    await update_source(page_path, bid, str(payload.get("source") or ""))
                    await reship_page()
                    return

                if op == "on_block_delete":
                    ids = _as_str_list(payload.get("block_ids"))
                    if not ids:
                        return
                    await delete_blocks(page_path, ids)
                    await reship_page()
                    return

                if op == "on_block_split":
                    # head stays in block_id; an optional `insert` block goes
                    # next; tail becomes a fresh prose block after that. One
                    # round trip so the page never renders a torn state.
                    bid = str(payload.get("block_id") or "")
                    if not bid:
                        return
                    await update_source(page_path, bid, str(payload.get("head") or ""))
                    anchor = bid
                    insert = payload.get("insert")
                    if isinstance(insert, dict):
                        anchor = await create_block(
                            page_path,
                            str(insert.get("kind") or KIND_PROGRAM),
                            str(insert.get("source") or ""),
                            anchor,
                        )
                    tail = str(payload.get("tail") or "")
                    if tail.strip() or not isinstance(insert, dict):
                        await create_block(page_path, KIND_PROSE, tail, anchor)
                    await reship_page()
                    return

                if op == "on_block_merge":
                    bid = str(payload.get("block_id") or "")
                    into = str(payload.get("into_id") or "")
                    if not bid or not into:
                        return
                    await update_source(page_path, into, str(payload.get("source") or ""))
                    await delete_blocks(page_path, [bid])
                    await reship_page()
                    return

                if op == "on_block_reorder":
                    ids = _as_str_list(payload.get("order"))
                    if not ids:
                        return
                    known = {sid for sid, _ in await read_blocks(page_path)}
                    ordered = [i for i in ids if i in known]
                    ordered += [i for i in known if i not in set(ordered)]
                    await renumber(page_path, ordered)
                    await reship_page()
                    return

                if op == "on_block_restart":
                    bid = str(payload.get("block_id") or "")
                    if not bid:
                        return
                    await supervisor.restart(bid)
                    return

            # -- boot --------------------------------------------------------

            # A virgin store has no root Page. init() only writes when the
            # slot is missing, so this is idempotent.
            try:
                await do_write(root.pages.init({"title": "", "sections": {}, "pages": {}}))
            except Exception:  # noqa: S110
                pass

            await ship_tree()
            await ship_page([])

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
                await supervisor.stop_all()
                sub.unbind(on_notify)
                sub.close()

        return athunk


def _as_str_list(raw: object) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(s) for s in raw]
