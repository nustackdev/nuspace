"""Everything the viewer and its panes say and hear, in the browser's own words.

- **Events**, browser to host. One path per op under ``<ref>.ops.``. The
  viewer hears one, ``planes.open``: which panes are open is a fact about
  the viewer. Everything a pane does rides its own path, so no event names
  its plane: the path says it.
- **Writes**, host to browser, on a pane's own path, tagged with an ``op``
  key. Five, each with what one watch changes: ``set_head`` (how the pane
  heads its plane), ``set_cells``, ``set_status``, ``set_trail`` and
  ``set_absent``. ``set_absent`` stands in for the head when the pane has
  no plane to draw, and a later ``set_head`` clears it. Any order is fine:
  the browser keeps each beside the others.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import BoolArg, ListArg, Nu, StrArg
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
    "on_delete_plane",
    "on_move_cell",
    "on_open",
    "on_remove_cell_key",
    "on_remove_plane_key",
    "on_rename_plane",
    "on_restart_cell",
    "on_restart_plane",
    "on_set_cell_key",
    "on_set_icon",
    "on_set_plane_key",
    "on_set_web",
    "on_update_cell",
    "set_absent",
    "set_cells",
    "set_head",
    "set_status",
    "set_trail",
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


# --- Writes: host -> pane -------------------------------------------------------


def set_head(
    pane: Ref,
    *,
    title: StrArg,
    icon: StrArg,
    key: StrArg,
    system: BoolArg,
    editable: BoolArg,
    width: StrArg,
) -> Nu:
    """Replace how the pane heads its plane: its name, icon and key, and how it shows.

    ``system`` is whether remove refuses the plane, so the pane offers no
    delete. ``editable`` and ``width`` are its web flags. Clears a
    :func:`set_absent`. Every open pane is answered with one or with a
    :func:`set_absent`, or it loads forever.
    """
    return write(
        pane,
        "set_head",
        title=title,
        icon=icon,
        key=key,
        system=system,
        editable=editable,
        width=width,
    )


def set_cells(pane: Ref, cells: ListArg[dict]) -> Nu:
    """Replace the pane's cells, in order, each ``{id, name, key, source, spec, draws, classes}``."""
    return write(pane, "set_cells", cells=cells)


def set_absent(pane: Ref, reason: StrArg) -> Nu:
    """Say the pane has nothing to draw, and why.

    ``reason`` is :data:`ABSENT_MISSING` or :data:`ABSENT_HEADLESS`. It
    stands in for the head; a later :func:`set_head` clears it.
    """
    return write(pane, "set_absent", reason=reason)


def set_status(pane: Ref, statuses: ListArg[dict]) -> Nu:
    """Say what each of the pane's cells is doing, each ``{cell_id, state, error, started_at}``."""
    return write(pane, "set_status", statuses=statuses)


def set_trail(pane: Ref, trail: ListArg[dict]) -> Nu:
    """Say which planes sit above the pane's, top first, each ``{id, title}``."""
    return write(pane, "set_trail", trail=trail)


# --- Events: browser -> viewer ----------------------------------------------------


def on_open(viewer: Ref) -> Changed:
    """The planes the browser has open, as panes, and their params. ``{plane_ids, params}``.

    The full ordered list every time, left to right, not a delta. ``params``
    is plane id to ``{key: str}``, one entry per pane.
    """
    return event(viewer, "planes.open")


# --- Events: browser -> pane --------------------------------------------------------
#
# The pane's plane is the path's, never a field.


def on_rename_plane(pane: Ref) -> Changed:
    """``{title}``. Renames the pane's plane."""
    return event(pane, "plane.rename")


def on_set_icon(pane: Ref) -> Changed:
    """``{icon}``: ``lucide:<name>``, ``emoji:<char>`` or ``""``."""
    return event(pane, "plane.icon")


def on_delete_plane(pane: Ref) -> Changed:
    """``{}``. Removes the pane's plane and everything under it."""
    return event(pane, "plane.delete")


def on_set_plane_key(pane: Ref) -> Changed:
    """``{key}``. Sets or changes the plane's key."""
    return event(pane, "plane.key")


def on_remove_plane_key(pane: Ref) -> Changed:
    """``{}``. Drops the plane's key, free for another plane."""
    return event(pane, "plane.remove_key")


def on_set_web(pane: Ref) -> Changed:
    """``{flags}``. Sets the plane's web flags given: ``editable``, ``width``."""
    return event(pane, "plane.web")


def on_restart_plane(pane: Ref) -> Changed:
    """``{}``. Runs the pane's plane again, a new plane run."""
    return event(pane, "plane.restart")


def on_create_cell(pane: Ref) -> Changed:
    """``{cell_id, name, before?, after?}``. Browser minted id.

    ``name`` names a CellSpec: the cell stores its source and takes its
    name. ``before`` or ``after`` is a cell of the plane, neither the end.
    """
    return event(pane, "cell.create")


def on_update_cell(pane: Ref) -> Changed:
    """``{cell_id, source}``. Replaces the prog, nothing else."""
    return event(pane, "cell.update")


def on_delete_cell(pane: Ref) -> Changed:
    """``{cell_id}``."""
    return event(pane, "cell.delete")


def on_move_cell(pane: Ref) -> Changed:
    """``{cell_id, before?, after?}``. Moves one cell among its plane's, neither anchor the end."""
    return event(pane, "cell.move")


def on_restart_cell(pane: Ref) -> Changed:
    """``{cell_id}``. Runs the cell again in this pane: a new cell run, or the pane's run when over."""
    return event(pane, "cell.restart")


def on_set_cell_key(pane: Ref) -> Changed:
    """``{cell_id, key}``. Sets or changes the cell's key."""
    return event(pane, "cell.key")


def on_remove_cell_key(pane: Ref) -> Changed:
    """``{cell_id}``. Drops the cell's key, free for another cell."""
    return event(pane, "cell.remove_key")
