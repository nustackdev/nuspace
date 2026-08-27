"""PagesRef -- nested page tree + section canvas over ``Space.pages``.

One ref owns the whole Pages tab, the way ``AppsRef`` owns the Apps tab.

- ``PagesRef``: a nu.ui Ref. Pure wire handle. Payload is stamped once
  in ``__init__`` (the ``space_root`` Shape class) and never mutated
  after -- all runtime state lives in the browser slice or in the
  driver's per-connection closure. Exposes two host-driven Write
  commands (``set_tree``, ``set_page``) plus ``feedback()``.

- ``PagesDriver``: Control. Per-connection. Ships the sidebar tree on
  mount, subscribes to this ref's wire path, dispatches each browser
  notify into substrate writes, and explicitly re-ships tree / page
  after every write it makes (nu has no deep-wildcard reactive
  subscription, so the driver owns the invalidation).

The driver also owns the *section body task*. A page's sections are Nu
snippets; when the browser is in display mode on a page, the driver
parses every section snippet, folds them with ``|``, and drives the
fold as a background asyncio task. Sections contain ``ReactForever``
so the fold never returns -- leaving the page or flipping to code mode
cancels the task. Exactly one section task is alive at a time.

Server-owned wire payloads (msgpack-native):

    write: {"op": "set_tree", "tree": PageNode}
    write: {"op": "set_page", "page_id": str|None, "path": [str],
            "title": str, "mode": "code"|"display",
            "sections": [SectionEntry]}

    PageNode     = {"id": str|None, "title": str, "pages": [PageNode]}
    SectionEntry = {"id": str, "name": str, "snippet": str,
                    "error": str|None, "fields": [MountField]}
    MountField   = {"path": str, "type": str, "props"?: dict}

Browser feedback (client -> server, all as ``notify`` frames on one
subscription, dispatched on ``payload["op"]``):

    {"op": "on_page_select",    "path": [pid...], "mode": "code"|"display"}
    {"op": "on_page_create",    "parent_path": [pid...], "title": str}
    {"op": "on_page_rename",    "path": [pid...], "title": str}
    {"op": "on_page_delete",    "path": [pid...]}
    {"op": "on_section_create", "page_path": [pid...], "name": str}
    {"op": "on_section_update", "page_path": [pid...], "section_id": str,
                                "name": str, "snippet": str}
    {"op": "on_section_delete", "page_path": [pid...], "section_id": str}

Section mounting is by section id as path prefix: each snippet is
parsed with ``path = "sections.<section_id>"`` in scope, so authors
namespace their ui refs under the section that owns them. Walking the
parsed term for ``nu.ui.Ref`` instances yields that section's mount
fields, which ship nested inside its ``set_page`` entry; the browser
slice registers them into the kit's ref map itself.

Snippets are parsed in Python here, not via ``Eval(PyCall(...))``.
``nu.prog.PyCall`` is deliberately uncommitted in nu and the mvp
documented that the PyCall variant hits an "Eval placed off the loop"
placement error under exactly this per-connection body path.
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
from nuspace.snippets import parse_snippet
from nuspace.web.server.page import _wire_type


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nu.domains.shape import Shape
    from nu.lang.runtime import Runtime


__all__ = ["PagesDriver", "PagesRef"]


# Hard caps, LensRef-style. No pagination in v1.
MAX_CHILD_PAGES = 200
MAX_PAGE_DEPTH = 12
MAX_SECTIONS = 100


# -- Ref ---------------------------------------------------------------------


class PagesRef(Ref):
    """Nested page tree + per-page section canvas over a Space's page root.

    Configured once with a ``space_root`` Shape class whose ``.pages``
    slot is a ``ShapeRef`` to the root ``Page``. The server owns the
    tree and the active-page payload; the browser owns the selection
    cursor (via the URL router), the code/display mode, the expanded
    set, and the per-section editor buffers.
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
        # Frozen: no runtime state ever lands on the payload. Mutating it
        # after construction bleeds across Nu tree rewrites that share the
        # payload reference (see the lens cursor-persistence bug).

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
        """Ship a pre-computed sidebar tree payload to the browser."""
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
    """Split ``[pid..., pid]`` into (parent ``PagesRef``, page_id)."""
    if not path:
        raise ValueError("page path is empty; the root page has no parent")
    return _page_ref(space_root, path[:-1]).pages, str(path[-1])


# -- Tree payload ------------------------------------------------------------


def _page_node(data: object, pid: str | None, depth: int) -> dict[str, Any]:
    """One sidebar node from an ``extract()`` blob. Sections are not shown."""
    if not isinstance(data, dict):
        return {"id": pid, "title": str(pid or ""), "pages": []}
    kids_raw = data.get("pages")
    kids: list[dict[str, Any]] = []
    if isinstance(kids_raw, dict) and depth < MAX_PAGE_DEPTH:
        for kid, blob in sorted(kids_raw.items())[:MAX_CHILD_PAGES]:
            kids.append(_page_node(blob, str(kid), depth + 1))
    return {
        "id": pid,
        "title": str(data.get("title") or (pid or "")),
        "pages": kids,
    }


# -- Section mounting --------------------------------------------------------


def _enumerate_ui_refs(term: nu.Nu, prefix: str) -> list[dict[str, Any]]:
    """Walk a Nu term, return one mount field per ``nu.ui.Ref`` it *owns*.

    Ported from the mvp. Deduplicated by ``(type, path)`` -- a snippet
    that touches the same InputRef twice (read + write) still produces
    one field. A bare ui Ref has no parent chain, so its wire path is
    exactly the segment string the snippet passed in, which is why
    ``parse_snippet`` seeds ``path = "sections.<section_id>"``.

    **Path is the mounting mechanism.** Only refs under ``prefix`` mount
    here. A snippet may freely name a ref belonging to another section
    (to read its value, or to write into it) -- that is a live
    cross-section wire and it keeps working, because both sections'
    terms run in the same folded tree against the same browser slices.
    But the section that *names* the path is the one that mounts it, so
    a borrowed ref renders once, in its owner, not again in every
    section that mentions it.
    """
    seen: set[tuple[str, str]] = set()
    fields: list[dict[str, Any]] = []
    own = prefix + "."

    def visit(node: object) -> None:
        if isinstance(node, nu.ui.Ref):
            segment = node._payload.get("segment")
            if isinstance(segment, str) and (segment == prefix or segment.startswith(own)):
                wire_type = _wire_type(type(node))
                key = (wire_type, segment)
                if key not in seen:
                    seen.add(key)
                    entry: dict[str, Any] = {"path": segment, "type": wire_type}
                    props = type(node)._mount_props()
                    if props:
                        entry["props"] = dict(props)
                    fields.append(entry)
        children = getattr(node, "_children", None)
        if children:
            for child in children:
                visit(child)

    visit(term)
    return fields


def _fold(terms: list[nu.Nu]) -> nu.Nu:
    """Fold section terms together with ``|`` (parallel)."""
    folded = terms[0]
    for term in terms[1:]:
        folded = folded | term
    return folded


# -- Driver ------------------------------------------------------------------


class PagesDriver(Control):
    """Per-connection driver: tree paint, feedback dispatch, section task.

    On boot it ships the sidebar tree. Then it loops on browser
    notifies, switching on ``payload["op"]``. Mutating handlers re-ship
    the tree and/or the active page explicitly -- ``on_descendants_change``
    needs a fixed-depth wildcard and cannot watch a recursive tree.

    The active page path + mode are loop-local closure state, not ref
    payload: they die with the connection, exactly like ``LensDriver``'s
    cursor. Reload restarts from whatever the browser's URL says.
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

            # Per-connection cursor. Closure-local, never on the payload.
            cursor: dict[str, Any] = {"path": [], "mode": "code"}
            section_task: asyncio.Task | None = None

            async def run(term: nu.Nu) -> Any:  # noqa: ANN401
                value, _ = await nu.arun(auto_flow_atomic(term, scope=root), rt.ctx)  # type: ignore[arg-type]
                return value

            async def do_write(term: nu.Nu) -> None:
                await run(term)

            async def stop_sections() -> None:
                nonlocal section_task
                task = section_task
                section_task = None
                if task is None or task.done():
                    return
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):  # noqa: S110
                    pass

            async def ship_tree() -> None:
                try:
                    data = await run(root.pages.extract())
                except Exception:
                    data = None
                tree = _page_node(data if isinstance(data, dict) else {}, None, 0)
                await session.send(
                    Frame("write", ref=wire_path, payload={"op": "set_tree", "tree": tree}),
                )

            async def ship_page(path: list[str], mode: str) -> None:
                nonlocal section_task
                await stop_sections()
                page = _page_ref(root, path)
                try:
                    raw_title = await run(page.title)
                except Exception:
                    raw_title = None
                # An unset StrRef reads back as a Nu sentinel, not "".
                title = raw_title if isinstance(raw_title, str) else ""
                try:
                    raw = await run(page.sections.extract())
                except Exception:
                    raw = None
                sections = raw if isinstance(raw, dict) else {}

                entries: list[dict[str, Any]] = []
                terms: list[nu.Nu] = []
                for sid, blob in sorted(sections.items())[:MAX_SECTIONS]:
                    if not isinstance(blob, dict):
                        continue
                    snippet = str(blob.get("snippet") or "")
                    entry: dict[str, Any] = {
                        "id": str(sid),
                        "name": str(blob.get("name") or sid),
                        "snippet": snippet,
                        "error": None,
                        "fields": [],
                    }
                    if mode == "display" and snippet.strip():
                        # One bad snippet degrades its own section only.
                        try:
                            prefix = f"sections.{sid}"
                            term = parse_snippet(snippet, prefix)
                            entry["fields"] = _enumerate_ui_refs(term, prefix)
                            terms.append(term)
                        except Exception as exc:
                            entry["error"] = f"{type(exc).__name__}: {exc}"
                    entries.append(entry)

                # Ship first so the browser has the field slices registered
                # before the running fold writes to them. Frames are ordered
                # on the ws, so this is enough.
                await session.send(
                    Frame(
                        "write",
                        ref=wire_path,
                        payload={
                            "op": "set_page",
                            "page_id": str(path[-1]) if path else None,
                            "path": list(path),
                            "title": title,
                            "mode": mode,
                            "sections": entries,
                        },
                    ),
                )
                if mode == "display" and terms:
                    body = auto_flow_atomic(_fold(terms), scope=root)
                    section_task = asyncio.create_task(nu.arun(body, rt.ctx))  # type: ignore[arg-type]

            async def reship_page() -> None:
                await ship_page(list(cursor["path"]), str(cursor["mode"]))

            # A virgin store has no root Page. init() only writes when the
            # slot is missing, so this is idempotent and keeps the tab
            # self-sufficient without a seed script.
            try:
                await do_write(root.pages.init({"title": "", "sections": {}, "pages": {}}))
            except Exception:  # noqa: S110
                pass

            await ship_tree()

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
                            space_root=root,
                            cursor=cursor,
                            do_write=do_write,
                            ship_page=ship_page,
                            reship_page=reship_page,
                            ship_tree=ship_tree,
                        )
                    except Exception:  # noqa: S110 -- one bad notify shouldn't die
                        pass
            finally:
                await stop_sections()
                sub.unbind(on_notify)
                sub.close()

        return athunk


async def _dispatch(
    payload: dict[str, Any],
    *,
    space_root: type[Shape],
    cursor: dict[str, Any],
    do_write: Callable[[nu.Nu], Awaitable[None]],
    ship_page: Callable[[list[str], str], Awaitable[None]],
    reship_page: Callable[[], Awaitable[None]],
    ship_tree: Callable[[], Awaitable[None]],
) -> None:
    """Route one browser notify into substrate writes plus explicit re-ships."""
    op = str(payload.get("op") or "")

    if op == "on_page_select":
        path = _as_str_list(payload.get("path"))
        mode = "display" if payload.get("mode") == "display" else "code"
        cursor["path"] = path
        cursor["mode"] = mode
        await ship_page(path, mode)
        return

    if op == "on_page_create":
        parent = _as_str_list(payload.get("parent_path"))
        title = str(payload.get("title") or "page")
        container = _page_ref(space_root, parent).pages
        await do_write(container.add(title=title, page_id=mint_ordered_id("p")))
        await ship_tree()
        return

    if op == "on_page_rename":
        path = _as_str_list(payload.get("path"))
        title = str(payload.get("title") or "page")
        await do_write(_page_ref(space_root, path).title.set(nu.Str(title)))
        await ship_tree()
        if path == list(cursor["path"]):
            await reship_page()
        return

    if op == "on_page_delete":
        path = _as_str_list(payload.get("path"))
        if not path:
            return  # the root page is structural; it cannot be deleted
        container, pid = _parent_pages(space_root, path)
        await do_write(container.del_item(pid))
        await ship_tree()
        if list(cursor["path"])[: len(path)] == path:
            # The active page just went away; fall back to its parent.
            cursor["path"] = path[:-1]
            await reship_page()
        return

    if op == "on_section_create":
        page_path = _as_str_list(payload.get("page_path"))
        name = str(payload.get("name") or "section")
        sections = _page_ref(space_root, page_path).sections
        await do_write(
            sections.add(
                name=name,
                snippet=str(payload.get("snippet") or ""),
                policy="on_navigate",
                section_id=mint_ordered_id("s"),
            ),
        )
        await reship_page()
        return

    if op == "on_section_update":
        page_path = _as_str_list(payload.get("page_path"))
        sid = str(payload.get("section_id") or "")
        if not sid:
            return
        sections = _page_ref(space_root, page_path).sections
        await do_write(
            sections.set_item(
                sid,
                {
                    "name": str(payload.get("name") or sid),
                    "snippet": str(payload.get("snippet") or ""),
                    "policy": "on_navigate",
                },
            ),
        )
        await reship_page()
        return

    if op == "on_section_delete":
        page_path = _as_str_list(payload.get("page_path"))
        sid = str(payload.get("section_id") or "")
        if not sid:
            return
        await do_write(_page_ref(space_root, page_path).sections.del_item(sid))
        await reship_page()
        return


def _as_str_list(raw: object) -> list[str]:
    if not isinstance(raw, (list, tuple)):
        return []
    return [str(s) for s in raw]
