"""The viewer: the open panes' planes, drawn, one pane per plane. One, never one per kind.

``ref``
    The node the browser draws, mounted with the registered CellSpecs, its ``/`` menu.
``interactions``
    Everything that node says and hears, in the browser's words.
``feed``
    One arm per interaction. An event runs one op, a store change ships the
    plane or the statuses again.
"""

from nuspace.devices.web.viewer.feed import (
    PROGRAM,
    WEB_FLAGS,
    plane_cells,
    plane_view,
    statuses,
    viewer_feed,
)
from nuspace.devices.web.viewer.interactions import (
    ABSENT_HEADLESS,
    ABSENT_MISSING,
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
    on_restart_cell,
    on_restart_plane,
    on_set_web,
    on_update_cell,
    set_absent,
    set_plane,
    set_status,
)
from nuspace.devices.web.viewer.ref import ViewerRef, slash_entries


__all__ = [
    "ABSENT_HEADLESS",
    "ABSENT_MISSING",
    "PROGRAM",
    "STATES",
    "STATE_FAILED",
    "STATE_IDLE",
    "STATE_RUNNING",
    "STATE_STARTING",
    "STATE_STOPPED",
    "WEB_FLAGS",
    "ViewerRef",
    "on_create_cell",
    "on_delete_cell",
    "on_move_cell",
    "on_open",
    "on_restart_cell",
    "on_restart_plane",
    "on_set_web",
    "on_update_cell",
    "plane_cells",
    "plane_view",
    "set_absent",
    "set_plane",
    "set_status",
    "slash_entries",
    "statuses",
    "viewer_feed",
]
