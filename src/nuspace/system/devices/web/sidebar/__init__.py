"""The sidebar: every plane that draws, grouped under the apps that made them.

``ref``
    The node the browser draws.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships the
    list again.
"""

from nuspace.system.devices.web.sidebar.feed import create_plane, rows, sections, sidebar_feed
from nuspace.system.devices.web.sidebar.interactions import (
    KIND_GROUP,
    KIND_PLANE,
    KIND_SPACE,
    KINDS,
    ROOT_ID,
    on_create_plane,
    on_delete_plane,
    on_move_plane,
    on_rename_plane,
    on_reorder_planes,
    set_tree,
)
from nuspace.system.devices.web.sidebar.ref import SidebarRef


__all__ = [
    "KINDS",
    "KIND_GROUP",
    "KIND_PLANE",
    "KIND_SPACE",
    "ROOT_ID",
    "SidebarRef",
    "create_plane",
    "on_create_plane",
    "on_delete_plane",
    "on_move_plane",
    "on_rename_plane",
    "on_reorder_planes",
    "rows",
    "sections",
    "set_tree",
    "sidebar_feed",
]
