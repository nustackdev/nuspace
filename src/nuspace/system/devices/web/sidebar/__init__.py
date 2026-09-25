"""The sidebar: every plane that draws, as one tree.

``ref``
    The node the browser draws, mounted with the registered Planes.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships the
    tree again.
"""

from nuspace.system.devices.web.sidebar.feed import create, move, node, rows, sidebar_feed
from nuspace.system.devices.web.sidebar.interactions import (
    KIND_PLANE,
    KIND_SPACE,
    KINDS,
    ROOT_ID,
    on_create_plane,
    on_delete_plane,
    on_move_plane,
    on_rename_plane,
    on_set_icon,
    set_tree,
)
from nuspace.system.devices.web.sidebar.ref import SidebarRef, registered_entries


__all__ = [
    "KINDS",
    "KIND_PLANE",
    "KIND_SPACE",
    "ROOT_ID",
    "SidebarRef",
    "create",
    "move",
    "node",
    "on_create_plane",
    "on_delete_plane",
    "on_move_plane",
    "on_rename_plane",
    "on_set_icon",
    "registered_entries",
    "rows",
    "set_tree",
    "sidebar_feed",
]
