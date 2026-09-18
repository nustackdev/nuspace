"""The sidebar as one node on the browser's tree.

:class:`SidebarRef` is a component ref like ``ButtonRef`` or ``InputRef``, only
wider: it renders the list of Planes that draw instead of a label. Same two
halves as any of them and nothing else, and every one of them is spelled once
in :mod:`nuspace.web.sidebar.interactions`. The ref holds no state. It reads
nothing, it remembers nothing and it knows about no store: everything it ships
is handed to it by whoever composed it.

One per tab, and it is the only thing that navigates.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nuspace.web.sidebar import interactions
from nuspace.web.utils import SpaceRef


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu
    from nustd.ui.core import Changed


__all__ = ["SidebarRef"]


class SidebarRef(SpaceRef):
    """Every Plane that draws, as one browser node."""

    _wire_type: ClassVar[str] = "SidebarRef"

    # --- writes: server -> browser -------------------------------------------

    def set_tree(self, planes: ListArg[dict]) -> Nu:
        """Replace the list: every Plane that draws, flat."""
        return interactions.set_tree(self, planes)

    # --- events: browser -> server -------------------------------------------

    def on_create_page(self) -> Changed:
        """``{page_id, parent_id, title}``. The browser minted ``page_id``."""
        return interactions.on_create_plane(self)

    def on_rename_page(self) -> Changed:
        """``{page_id, title}``."""
        return interactions.on_rename_plane(self)

    def on_delete_page(self) -> Changed:
        """``{page_id}``."""
        return interactions.on_delete_plane(self)

    def on_move_page(self) -> Changed:
        """``{page_id, parent_id, index}``. Reparent, landing at ``index``."""
        return interactions.on_move_plane(self)

    def on_reorder_pages(self) -> Changed:
        """``{parent_id, page_ids}``. One parent's children, in the new order."""
        return interactions.on_reorder_planes(self)
