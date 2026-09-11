"""One connection's view of the Pages surface.

A ``View`` is what the interactions in ``interactions/`` are written
against: it holds this connection's supervisor, its cursor, and the
debounced flags that decide when a frame goes out. It is per connection
and dies with it, exactly like the run it belongs to.

## The cursor

``Cursor.path`` is a ``nu.mem`` ref, provided under this connection's
Context by ``control.py``. It used to be a python dict in the driver's
closure, which is the thing ``architecture.md`` calls out by name: a view
preference living beside the program instead of in it.

Why the server holds a cursor at all: the browser owns navigation (the
URL is the truth), but the server has to know which page *this*
connection is looking at in order to ship it and to supervise its
sections. That is real state with a real lifetime, so it belongs in a
fabric, not in a closure.

Why ``nu.mem`` and not the other two options:

- a kv ref would put one tab's cursor in shared storage, where every
  other tab would see it. Two tabs on two pages is the normal case.
- a ui ref would put it on the wire, and the browser would be round
  tripping its own URL back to itself to read it.
- ``nu.mem`` is per run, bound on Context under a tag, and dies when the
  connection's ``arun`` unwinds. That is the cursor's lifetime exactly.

It is stored as a ``"/"``-joined string rather than a list because
``PrimitiveListRef.append`` is currently a silent no-op in nu, and
because the empty string is a clean spelling of "the root page".
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nu.mem
from nu.kv.tree import auto_flow_atomic
from nuspace.web.refs.common import Dirty, StatusRelay
from nuspace.web.refs.pages.store import (
    KIND_PROGRAM,
    MAX_BLOCKS,
    ORDER_STEP,
    kind_of,
    ordered_blocks,
    page_node,
    page_ref,
)
from nuspace.web.refs.pages.supervise import LocalSupervisor, SectionSpec


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang import Context


__all__ = ["Cursor", "View"]


class Cursor(nu.Shape):
    """This connection's page cursor. Per run, dies with the connection."""

    path = nu.mem.StrRef.slot()


class View:
    """Per-connection state the Pages interactions read and write."""

    def __init__(self, ctx: Context, root: type[Shape]) -> None:
        self.ctx = ctx
        self.root = root
        self.supervisor = LocalSupervisor(ctx, root)
        self.tree_dirty = Dirty()
        self.page_dirty = Dirty()
        self.status = StatusRelay()
        self.supervisor.on_change(self.status.push)
        self._last_tree: dict[str, Any] | None = None
        self._last_page: dict[str, Any] | None = None

    # -- evaluation ----------------------------------------------------------

    async def run(self, term: nu.Nu) -> Any:  # noqa: ANN401 -- kv values are opaque
        """Evaluate one Nu term against this space's storage."""
        value, _ = await nu.arun(auto_flow_atomic(term, scope=self.root), self.ctx)  # type: ignore[arg-type]
        return value

    async def write(self, term: nu.Nu) -> None:
        """Evaluate a term for its effect and drop the value."""
        await self.run(term)

    async def read(self, term: nu.Nu, default: Any = None) -> Any:  # noqa: ANN401
        """Evaluate a term, answering ``default`` if the read blows up.

        A slot that was never written reads back as a Nu sentinel and an
        address through a missing container raises. Neither is worth a
        traceback on a surface whose whole job is to paint what is there.
        """
        try:
            return await self.run(term)
        except Exception:
            return default

    # -- cursor --------------------------------------------------------------

    async def cursor(self) -> list[str]:
        """The page path this connection is looking at. Empty = root."""
        value, _ = await nu.arun(Cursor.path, self.ctx)  # type: ignore[arg-type]
        if not isinstance(value, str) or not value:
            return []
        return value.split("/")

    async def set_cursor(self, path: list[str]) -> None:
        """Point this connection at ``path``."""
        await nu.arun(Cursor.path.set(nu.Str("/".join(path))), self.ctx)  # type: ignore[arg-type]

    # -- invalidation --------------------------------------------------------

    async def invalidate(self, key: object = None) -> None:
        """Mark both payloads stale. Called per kv notification.

        Both, not one: a title write changes the rail, a section write
        changes the canvas, and a page move changes both. Telling them
        apart from the key alone means re-deriving the cursor's subtree
        on every notification, which costs more than the dedupe in
        ``next_tree`` / ``next_page`` already saves. ``key`` is the full
        absolute kv key and is here for whoever wants to get cleverer.
        """
        del key
        self.tree_dirty.mark()
        self.page_dirty.mark()

    # -- payloads ------------------------------------------------------------

    async def next_tree(self) -> dict[str, Any]:
        """Wait until the rail has something new to say, then say it.

        Two filters, and both earn their keep. Time coalesces a burst
        into one read; value drops a read that came back identical, and
        loops back to waiting rather than shipping a frame the browser
        would apply over itself. A notification storm over content
        nobody is looking at therefore costs one read and no frames.
        """
        while True:
            await self.tree_dirty.settled()
            data = await self.read(self.root.pages.extract())
            tree = page_node(data if isinstance(data, dict) else {}, None, 0)
            payload = {"op": "set_tree", "tree": tree}
            if payload != self._last_tree:
                self._last_tree = payload
                return payload

    async def next_page(self) -> dict[str, Any]:
        """Wait until the canvas has something new, then build its payload.

        Reconciles supervision to this page's program blocks on the way
        through, so the payload carries live mount fields and live
        status. Nothing is started here -- ``plan`` compiles and returns,
        and ``launch`` runs after the frame is on the wire, so a section
        can never write to a slice the browser has not registered yet.
        """
        while True:
            await self.page_dirty.settled()
            payload = await self.page_payload()
            if payload is not None:
                return payload

    async def page_payload(self) -> dict[str, Any] | None:
        """Build the active page's payload now. ``None`` if unchanged."""
        path = await self.cursor()
        items = await self.blocks(path)
        page = page_ref(self.root, path)
        raw_title = await self.read(page.title)
        # An unset StrRef reads back as a Nu sentinel, not "".
        title = raw_title if isinstance(raw_title, str) else ""

        self.supervisor.plan(
            [
                SectionSpec(sid, str(blob.get("snippet") or ""))
                for sid, blob in items
                if kind_of(blob) == KIND_PROGRAM
            ],
        )

        blocks: list[dict[str, Any]] = []
        for index, (sid, blob) in enumerate(items):
            kind = kind_of(blob)
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
                entry["fields"] = self.supervisor.fields(sid)
                entry["status"] = self.supervisor.status(sid)
            blocks.append(entry)

        payload = {
            "op": "set_page",
            "page_id": str(path[-1]) if path else None,
            "path": list(path),
            "title": title,
            "blocks": blocks,
        }
        if payload == self._last_page:
            return None
        self._last_page = payload
        return payload

    async def next_status(self) -> dict[str, Any]:
        """Wait for the next status burst, return it as one frame."""
        return {"op": "set_status", "statuses": await self.status.batch()}

    # -- reads ---------------------------------------------------------------

    async def blocks(self, path: list[str]) -> list[tuple[str, dict[str, Any]]]:
        """This page's blocks, ordered, capped."""
        raw = await self.read(page_ref(self.root, path).sections.extract())
        return ordered_blocks(raw)[:MAX_BLOCKS]

    # -- lifecycle -----------------------------------------------------------

    async def launch(self) -> None:
        """Start whatever the last ``plan`` left pending."""
        await self.supervisor.launch()

    def forget_page(self) -> None:
        """Drop the cached page payload so the next build always ships."""
        self._last_page = None

    async def dispose(self) -> None:
        """Bounded teardown of every section this connection was running."""
        await self.supervisor.stop_all()
