"""The viewer: the open plane's cells, drawn. One, never one per kind.

``ref``
    The node the browser draws, mounted with the snippets' starters.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships the
    page or the statuses again.
"""

from nuspace.system.devices.web.viewer.feed import (
    PROSE,
    blocks,
    page,
    prose_source,
    statuses,
    viewer_feed,
)
from nuspace.system.devices.web.viewer.interactions import (
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
    STATES,
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
from nuspace.system.devices.web.viewer.ref import ViewerRef, starters


__all__ = [
    "PROSE",
    "STATES",
    "STATE_FAILED",
    "STATE_IDLE",
    "STATE_RUNNING",
    "STATE_STARTING",
    "STATE_STOPPED",
    "TPL_PROGRAM",
    "TPL_TEXT",
    "ViewerRef",
    "blocks",
    "on_create_cell",
    "on_delete_cell",
    "on_move_cell",
    "on_reorder_cells",
    "on_select",
    "on_update_cell",
    "page",
    "prose_source",
    "set_page",
    "set_status",
    "starters",
    "statuses",
    "viewer_feed",
]
