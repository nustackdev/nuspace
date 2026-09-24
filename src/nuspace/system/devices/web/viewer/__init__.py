"""The viewer: the open planes' cells, drawn, one pane per plane. One, never one per kind.

``ref``
    The node the browser draws, mounted with the snippets' ``/`` menu.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships the
    page or the statuses again.
"""

from nuspace.system.devices.web.viewer.feed import PAGE_META, blocks, page, statuses, viewer_feed
from nuspace.system.devices.web.viewer.interactions import (
    STATE_FAILED,
    STATE_IDLE,
    STATE_RUNNING,
    STATE_STARTING,
    STATE_STOPPED,
    STATES,
    on_create_cell,
    on_delete_cell,
    on_move_cell,
    on_open,
    on_reorder_cells,
    on_set_meta,
    on_update_cell,
    set_page,
    set_status,
)
from nuspace.system.devices.web.viewer.ref import ViewerRef, slash_entries


__all__ = [
    "PAGE_META",
    "STATES",
    "STATE_FAILED",
    "STATE_IDLE",
    "STATE_RUNNING",
    "STATE_STARTING",
    "STATE_STOPPED",
    "ViewerRef",
    "blocks",
    "on_create_cell",
    "on_delete_cell",
    "on_move_cell",
    "on_open",
    "on_reorder_cells",
    "on_set_meta",
    "on_update_cell",
    "page",
    "set_page",
    "set_status",
    "slash_entries",
    "statuses",
    "viewer_feed",
]
