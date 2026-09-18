"""The prose viewer: a Plane as a document, its Cells as the blocks in it.

A rail of every Plane on the left and one Plane's Cells down the middle, each
Cell either prose somebody is writing or a program somebody is editing. The
page render nuspace has always had, and the viewer every other one is measured
against.

Three files, which is what a viewer is:

``ref.py``
    The node the browser draws, where a Cell's own refs land under it, and
    what a Cell holds when it is prose rather than a program.
``interactions.py``
    Everything that node says and hears, in the browser's own words.
``driver.py``
    One arm per interaction. A browser event runs one op; a store change ships
    one write back.

Where a Cell's refs land is :mod:`nuspace.web.utils` rather than here, because
the rewrite is the same sentence for any viewer that draws Cells and only the
address under the surface is this one's.
"""

from nuspace.web.viewers.prose.driver import ARMS, prose_driver
from nuspace.web.viewers.prose.interactions import (
    TPL_PROGRAM,
    TPL_TEXT,
    on_create_cell,
    on_create_plane,
    on_delete_cell,
    on_delete_plane,
    on_move_cell,
    on_move_plane,
    on_rename_plane,
    on_reorder_cells,
    on_reorder_planes,
    on_select,
    on_update_cell,
    set_page,
    set_status,
    set_tree,
)
from nuspace.web.viewers.prose.ref import PROSE, PagesRef, prose_source, starters


__all__ = [
    "ARMS",
    "PROSE",
    "TPL_PROGRAM",
    "TPL_TEXT",
    "PagesRef",
    "on_create_cell",
    "on_create_plane",
    "on_delete_cell",
    "on_delete_plane",
    "on_move_cell",
    "on_move_plane",
    "on_rename_plane",
    "on_reorder_cells",
    "on_reorder_planes",
    "on_select",
    "on_update_cell",
    "prose_driver",
    "prose_source",
    "set_page",
    "set_status",
    "set_tree",
    "starters",
]
