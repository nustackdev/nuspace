"""The sidebar as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders the list of planes
that draw. It holds no state and knows no store; everything it ships is
handed to it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nuspace.system.devices.web.sidebar import interactions
from nuspace.system.devices.web.utils import SpaceRef


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu
    from nustd.ui.core import Changed


__all__ = ["SidebarRef"]


class SidebarRef(SpaceRef):
    """Every plane that draws, as one browser node."""

    _wire_type: ClassVar[str] = "SidebarRef"

    def set_tree(self, rows: ListArg[dict]) -> Nu:
        """Replace the list."""
        return interactions.set_tree(self, rows)

    def on_create_page(self) -> Changed:
        """``{page_id, parent_id, group, title}``."""
        return interactions.on_create_plane(self)

    def on_rename_page(self) -> Changed:
        """``{page_id, title}``."""
        return interactions.on_rename_plane(self)

    def on_delete_page(self) -> Changed:
        """``{page_id}``."""
        return interactions.on_delete_plane(self)

    def on_move_page(self) -> Changed:
        """``{page_id, parent_id, index}``."""
        return interactions.on_move_plane(self)

    def on_reorder_pages(self) -> Changed:
        """``{parent_id, page_ids}``."""
        return interactions.on_reorder_planes(self)
