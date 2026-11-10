"""Everything the viewer says and hears, in the browser's own words.

- **Events**, browser to host. One path per op under ``<viewer>.ops.``.
- **Writes**, host to browser. Three, on the viewer's own path, tagged with an
  ``op`` key, and keyed by ``plane_id``: several planes can be open at once,
  one pane each. ``set_status`` patches what ``set_plane`` landed for the
  same plane, so the two go in that order. ``set_absent`` stands in for
  ``set_plane`` when the pane has no plane to draw; either replaces the other.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`. ``planes.open`` is the viewer's: which panes are open is a
fact about the viewer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.devices.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import DictArg, ListArg, Nu, StrArg
    from nustd.ui.core import Changed, Ref


__all__ = [
    "ABSENT_HEADLESS",
    "ABSENT_MISSING",
    "STATES",
    "STATE_FAILED",
    "STATE_IDLE",
    "STATE_RUNNING",
    "STATE_STARTING",
    "STATE_STOPPED",
    "on_create_cell",
    "on_delete_cell",
    "on_move_cell",
    "on_open",
    "on_remove_cell_key",
    "on_remove_plane_key",
    "on_restart_cell",
    "on_restart_plane",
    "on_set_cell_key",
    "on_set_plane_key",
    "on_set_web",
    "on_update_cell",
    "set_absent",
    "set_plane",
    "set_status",
]


#: Nothing running, and nothing wrong the last time.
STATE_IDLE = "idle"

#: Asked for, not up yet.
STATE_STARTING = "starting"

#: Up, or on its way down.
STATE_RUNNING = "running"

#: Asked to stop, or killed.
STATE_STOPPED = "stopped"

#: Raised, or its worker died under it.
STATE_FAILED = "failed"

#: What a cell's status can say. The browser's contract (``types.ts``).
STATES = (STATE_IDLE, STATE_STARTING, STATE_RUNNING, STATE_STOPPED, STATE_FAILED)

#: No plane by that id.
ABSENT_MISSING = "missing"

#: A plane, but not on the web: no tab shows it.
ABSENT_HEADLESS = "headless"


# --- Writes: host -> browser --------------------------------------------------


def set_plane(
    viewer: Ref,
    plane_id: StrArg,
    *,
    title: StrArg,
    meta: DictArg[str, object],
    cells: ListArg[dict],
) -> Nu:
    """Replace what one pane draws: one plane and its cells, in order.

    ``meta`` is how the pane shows it: its web flags (``editable``,
    ``full_width``, ``compact``), its ``icon`` and its ``key``. A cell is ``{id, name,
    key, source, spec, draws, classes}``. Every open plane is answered
    with one or with a :func:`set_absent`, or its pane loads forever.
    """
    return write(viewer, "set_plane", plane_id=plane_id, title=title, meta=meta, cells=cells)


def set_absent(viewer: Ref, plane_id: StrArg, reason: StrArg) -> Nu:
    """Say one pane has nothing to draw, and why.

    ``reason`` is :data:`ABSENT_MISSING` or :data:`ABSENT_HEADLESS`. A later
    :func:`set_plane` for the same plane replaces it.
    """
    return write(viewer, "set_absent", plane_id=plane_id, reason=reason)


def set_status(viewer: Ref, plane_id: StrArg, statuses: ListArg[dict]) -> Nu:
    """Patch what one pane says about its cells.

    An entry is ``{cell_id, state, error, started_at}``. A patch into the
    plane already landed, so it follows a :func:`set_plane` for the same plane.
    """
    return write(viewer, "set_status", plane_id=plane_id, statuses=statuses)


# --- Events: browser -> host --------------------------------------------------


def on_open(viewer: Ref) -> Changed:
    """The planes the browser has open, as panes, and their params. ``{plane_ids, params}``.

    The full ordered list every time, left to right, not a delta. ``params``
    is plane id to ``{key: str}``, one entry per pane.
    """
    return event(viewer, "planes.open")


def on_create_cell(viewer: Ref) -> Changed:
    """``{plane_id, cell_id, name, before?, after?}``. Browser minted id.

    ``name`` names a CellSpec: the cell stores its source and takes its
    name. ``before`` or ``after`` is a cell of the plane, neither the end.
    """
    return event(viewer, "cell.create")


def on_update_cell(viewer: Ref) -> Changed:
    """``{cell_id, source}``. Replaces the prog, nothing else."""
    return event(viewer, "cell.update")


def on_delete_cell(viewer: Ref) -> Changed:
    """``{cell_id}``."""
    return event(viewer, "cell.delete")


def on_move_cell(viewer: Ref) -> Changed:
    """``{cell_id, before?, after?}``. Moves one cell among its plane's, neither anchor the end."""
    return event(viewer, "cell.move")


def on_restart_cell(viewer: Ref) -> Changed:
    """``{cell_id}``. Runs the cell again in this tab's pane: a new cell run, or the pane's run when over."""
    return event(viewer, "cell.restart")


def on_restart_plane(viewer: Ref) -> Changed:
    """``{plane_id}``. Runs this pane's plane again, a new plane run."""
    return event(viewer, "plane.restart")


def on_set_cell_key(viewer: Ref) -> Changed:
    """``{cell_id, key}``. Sets or changes the cell's key."""
    return event(viewer, "cell.key")


def on_remove_cell_key(viewer: Ref) -> Changed:
    """``{cell_id}``. Drops the cell's key, free for another cell."""
    return event(viewer, "cell.remove_key")


def on_set_plane_key(viewer: Ref) -> Changed:
    """``{plane_id, key}``. Sets or changes the plane's key."""
    return event(viewer, "plane.key")


def on_remove_plane_key(viewer: Ref) -> Changed:
    """``{plane_id}``. Drops the plane's key, free for another plane."""
    return event(viewer, "plane.remove_key")


def on_set_web(viewer: Ref) -> Changed:
    """``{plane_id, flags}``. Sets the plane's web flags given: ``editable``, ``full_width``, ``compact``."""
    return event(viewer, "plane.web")
