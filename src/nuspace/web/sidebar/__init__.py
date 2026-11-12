"""The sidebar: the web planes, as one lazy tree per tab.

``ref``
    The node the browser draws, mounted with the registered PlaneSpecs.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships the
    tree again.
"""

from nuspace.web.sidebar.feed import create, node, rows, sidebar_feed
from nuspace.web.sidebar.interactions import (
    KIND_PLANE,
    KIND_SPACE,
    KINDS,
    ROOT_ID,
    on_collapse,
    on_create_plane,
    on_delete_plane,
    on_expand,
    on_move_plane,
    on_rename_plane,
    on_set_icon,
    set_tree,
)
from nuspace.web.sidebar.ref import SidebarRef, registered_entries


__all__ = [
    "KINDS",
    "KIND_PLANE",
    "KIND_SPACE",
    "ROOT_ID",
    "SidebarRef",
    "create",
    "node",
    "on_collapse",
    "on_create_plane",
    "on_delete_plane",
    "on_expand",
    "on_move_plane",
    "on_rename_plane",
    "on_set_icon",
    "registered_entries",
    "rows",
    "set_tree",
    "sidebar_feed",
]
