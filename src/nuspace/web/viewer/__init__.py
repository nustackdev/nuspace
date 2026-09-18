"""The Viewer: one Plane's Cells, drawn. One, never one per kind.

It is the shell for a Plane's Nu ui code and it never asks what kind of thing
it is drawing. What makes a prose Plane look like prose is the programs in its
Cells. The one bit it reads off the Plane is ``editable``, which says whether
the controls a document has are drawn beside those Cells.

Three files, the same shape the sidebar has:

``ref.py``
    The node the browser draws, and what a Cell holds when it is prose rather
    than a program.
``interactions.py``
    Everything that node says and hears, in the browser's own words.
``driver.py``
    One arm per interaction. A browser event runs one op; a store change ships
    one write back.

Where a Cell's refs land is :mod:`nuspace.web.utils` rather than here, because
the rewrite is the same sentence wherever Cells are drawn and only the address
under the Viewer is this one's.
"""

from nuspace.web.viewer.driver import ARMS, viewer_driver
from nuspace.web.viewer.interactions import (
    TPL_PROGRAM,
    TPL_TEXT,
    on_create_cell,
    on_delete_cell,
    on_move_cell,
    on_reorder_cells,
    on_select,
    on_update_cell,
    set_page,
    set_status,
)
from nuspace.web.viewer.ref import PROSE, ViewerRef, prose_source, starters


__all__ = [
    "ARMS",
    "PROSE",
    "TPL_PROGRAM",
    "TPL_TEXT",
    "ViewerRef",
    "on_create_cell",
    "on_delete_cell",
    "on_move_cell",
    "on_reorder_cells",
    "on_select",
    "on_update_cell",
    "prose_source",
    "set_page",
    "set_status",
    "starters",
    "viewer_driver",
]
