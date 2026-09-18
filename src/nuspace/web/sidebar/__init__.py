"""The sidebar: every Plane that draws, as one list. One per tab.

Nothing else navigates. A Plane says ``ui`` and it is a row in here, and
picking a row is what the Viewer opens.

Three files, the same shape the Viewer has:

``ref.py``
    The node the browser draws.
``interactions.py``
    Everything that node says and hears, in the browser's own words.
``driver.py``
    One arm per interaction. A browser event runs one op; a store change ships
    the list again.

Every write it makes is a :mod:`nuspace.ops` call. There is no ``ops.py`` here
and there is not one under the Viewer either: one Plane write, one place.
"""

from nuspace.web.sidebar.driver import ARMS, ROOT_ID, rows, sidebar_driver
from nuspace.web.sidebar.interactions import (
    on_create_plane,
    on_delete_plane,
    on_move_plane,
    on_rename_plane,
    on_reorder_planes,
    set_tree,
)
from nuspace.web.sidebar.ref import SidebarRef


__all__ = [
    "ARMS",
    "ROOT_ID",
    "SidebarRef",
    "on_create_plane",
    "on_delete_plane",
    "on_move_plane",
    "on_rename_plane",
    "on_reorder_planes",
    "rows",
    "set_tree",
    "sidebar_driver",
]
