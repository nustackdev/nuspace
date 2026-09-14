"""``PagesRef`` -- the pages surface as one nu.ui Ref.

A component ref like ``ButtonRef`` or ``InputRef``, only wider: it renders a
page rail and a section canvas instead of a label. Same two halves as any of
them, and nothing else.

- **Events**, browser -> server. One subscription per op, each on its own
  wire path under ``<ref>.ops.``. The path is the discrimination, so the
  server binds one arm per op instead of switching on a string in a payload,
  and a browser that spells an op wrong notifies into a path nobody is
  listening on rather than into somebody else's handler.
- **Writes**, server -> browser. ``set_tree`` / ``set_page`` / ``set_status``,
  all on the ref's own path, all tagged with ``op`` -- the browser slice is
  registered per mount path and a write to a path with no slice is dropped,
  which is why these three cannot each take a path of their own the way the
  events do.

The ref holds no state. It reads nothing, it remembers nothing, and it knows
about no store: every value it ships is handed to it by whoever composed it.
What each event means in kv is :mod:`nuspace.pages.ops`, and which op is
wired to which arm is :mod:`nuspace.web.pages.driver`.

**Ids are minted by the browser.** ``page.create`` and ``section.create``
carry the id of the thing being made. A create is then a pure function of its
event, so re-running the arm rewrites one row instead of adding another, and
the browser can route to what it just made without waiting to be told its
name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace._root import resolve_root
from nuspace.core.tpl import TPLS
from nuspace.core.ui import SpaceRef
from nuspace.web.wire import event, write


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang import ListArg, Nu, StrArg
    from nu.ui.core import Changed


__all__ = ["PagesRef", "starters"]


def starters(root: type[Shape] | None = None) -> dict[str, str]:
    """What a block of each tpl starts life as, keyed by tpl name.

    Shipped in the mount so the browser can fill ``source`` on a create
    without owning a second copy of the template. ``nuspace.core.tpl`` stays
    the one spelling of it.
    """
    space = resolve_root(root)
    return {name: tpl.source(space) for name, tpl in TPLS.items()}


class PagesRef(SpaceRef):
    """The page tree and one page's sections, as one browser surface."""

    _wire_type: ClassVar[str] = "PagesRef"

    @classmethod
    def slot(cls, *, root: type[Shape] | None = None) -> Self:
        """Mount the surface, seeded with what a new block starts life as.

        Args:
            root: the space's root Shape class. A templated block's program
                names it, so the starters cannot be written until it is known.
        """
        return super().slot(starters=starters(root))

    # --- writes: server -> browser -------------------------------------------

    def set_tree(self, pages: ListArg[dict]) -> Nu:
        """Replace the rail: every page in the space, flat.

        Each row is ``{id, title, parent, children}``. The hierarchy is
        ``parent`` and ``children``, so the browser is handed the same shape
        the store holds and builds no second one.
        """
        return write(self, "set_tree", pages=pages)

    def set_page(
        self,
        page_id: StrArg,
        *,
        title: StrArg,
        parent: StrArg,
        children: ListArg[str],
        blocks: ListArg[dict],
    ) -> Nu:
        """Replace the canvas: one page, and its sections in order.

        Each block is ``{id, name, source, tpl, policy}``. Order is list
        position, here as in the store.
        """
        return write(
            self,
            "set_page",
            page_id=page_id,
            title=title,
            parent=parent,
            children=children,
            blocks=blocks,
        )

    def set_status(self, statuses: ListArg[dict]) -> Nu:
        """Patch what the canvas says about its sections.

        Each entry is ``{section_id, state, error, started_at}``. A patch,
        not a replacement: a section the batch does not name keeps whatever
        it was showing.
        """
        return write(self, "set_status", statuses=statuses)

    # --- events: browser -> server -------------------------------------------

    def on_select(self) -> Changed:
        """The browser navigated to a page. ``{page_id}``."""
        return self._on("page.select")

    def on_create_page(self) -> Changed:
        """``{page_id, parent_id, title}``. The browser minted ``page_id``."""
        return self._on("page.create")

    def on_rename_page(self) -> Changed:
        """``{page_id, title}``."""
        return self._on("page.rename")

    def on_delete_page(self) -> Changed:
        """``{page_id}``. Takes the whole subtree with it."""
        return self._on("page.delete")

    def on_move_page(self) -> Changed:
        """``{page_id, parent_id, index}``. Reparent, landing at ``index``."""
        return self._on("page.move")

    def on_reorder_pages(self) -> Changed:
        """``{parent_id, page_ids}``. One parent's children, in the new order."""
        return self._on("page.reorder")

    def on_create_section(self) -> Changed:
        """``{page_id, section_id, name, tpl, source, index}``. Browser-minted id."""
        return self._on("section.create")

    def on_update_section(self) -> Changed:
        """``{page_id, section_id, source}``. Replaces the source, nothing else."""
        return self._on("section.update")

    def on_delete_section(self) -> Changed:
        """``{page_id, section_id}``."""
        return self._on("section.delete")

    def on_move_section(self) -> Changed:
        """``{page_id, section_id, to_page_id, index}``. Keeps the section's id."""
        return self._on("section.move")

    def on_reorder_sections(self) -> Changed:
        """``{page_id, section_ids}``. One page's sections, in the new order."""
        return self._on("section.reorder")

    # --- addressing ----------------------------------------------------------

    def _on(self, op: str) -> Changed:
        """Subscribe to ``<this ref>.ops.<op>``."""
        return event(self, op)
