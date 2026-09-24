"""Everything the viewer says and hears, in the browser's own words.

Every name here is the wire spelling: a plane is a ``page``, a cell a
``section``.

- **Events**, browser to host. One path per op under ``<viewer>.ops.``.
- **Writes**, host to browser. Two, on the viewer's own path, tagged with an
  ``op`` key, and keyed by ``page_id``: several planes can be open at once,
  one pane each. ``set_status`` patches what ``set_page`` landed for the same
  page, so the two go in that order.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`. ``pages.open`` is the viewer's: which panes are open is a
fact about the viewer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.system.devices.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import DictArg, ListArg, Nu, StrArg
    from nustd.ui.core import Changed, Ref


__all__ = [
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
    "on_reorder_cells",
    "on_set_meta",
    "on_update_cell",
    "set_page",
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


# --- Writes: host -> browser --------------------------------------------------


def set_page(
    viewer: Ref,
    plane_id: StrArg,
    *,
    title: StrArg,
    meta: DictArg[str, object],
    cells: ListArg[dict],
) -> Nu:
    """Replace what one pane draws: one plane and its cells, in order.

    ``meta`` is the plane's whole meta, ``editable`` and ``full_width`` at
    least. A cell is ``{id, name, source}``. Every open plane is answered
    with one, even for something that is not a plane, or its pane loads
    forever.
    """
    return write(viewer, "set_page", page_id=plane_id, title=title, meta=meta, blocks=cells)


def set_status(viewer: Ref, plane_id: StrArg, statuses: ListArg[dict]) -> Nu:
    """Patch what one pane says about its cells.

    An entry is ``{section_id, state, error, started_at}``. A patch into the
    page already landed, so it follows a :func:`set_page` for the same plane.
    """
    return write(viewer, "set_status", page_id=plane_id, statuses=statuses)


# --- Events: browser -> host --------------------------------------------------


def on_open(viewer: Ref) -> Changed:
    """The planes the browser has open, as panes. ``{page_ids}``.

    The full ordered list every time, left to right, not a delta.
    """
    return event(viewer, "pages.open")


def on_create_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, name, index}``. Browser minted id.

    ``name`` names a snippet: the cell stores its prog and takes its name.
    """
    return event(viewer, "section.create")


def on_update_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, source}``. Replaces the prog, nothing else."""
    return event(viewer, "section.update")


def on_delete_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id}``."""
    return event(viewer, "section.delete")


def on_move_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, to_page_id, index}``. Keeps the cell's id."""
    return event(viewer, "section.move")


def on_reorder_cells(viewer: Ref) -> Changed:
    """``{page_id, section_ids}``. One plane's cells, in the new order."""
    return event(viewer, "section.reorder")


def on_set_meta(viewer: Ref) -> Changed:
    """``{page_id, meta}``. Merges ``meta``'s keys into the plane's meta, shallow."""
    return event(viewer, "page.meta")
