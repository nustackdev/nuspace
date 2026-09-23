"""Everything the viewer says and hears, in the browser's own words.

Every name here is the wire spelling: a plane is a ``page``, a cell a
``section``.

- **Events**, browser to host. One path per op under ``<viewer>.ops.``.
- **Writes**, host to browser. Two, on the viewer's own path, tagged with an
  ``op`` key. ``set_status`` patches what ``set_page`` landed, so the two go
  in that order.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`. ``page.select`` is the viewer's: what the URL names is a fact
about what the viewer has open.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.system.devices.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import BoolArg, ListArg, Nu, StrArg
    from nustd.ui.core import Changed, Ref


__all__ = [
    "STATES",
    "STATE_FAILED",
    "STATE_IDLE",
    "STATE_RUNNING",
    "STATE_STARTING",
    "STATE_STOPPED",
    "TPL_PROGRAM",
    "TPL_TEXT",
    "on_create_cell",
    "on_delete_cell",
    "on_move_cell",
    "on_reorder_cells",
    "on_select",
    "on_update_cell",
    "set_page",
    "set_status",
]


#: A cell the person writes prose into: a document surface.
TPL_TEXT = "text"

#: A cell the person writes a program into. Anything not :data:`TPL_TEXT`.
TPL_PROGRAM = "program"

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


# --- writes: host -> browser --------------------------------------------------


def set_page(
    viewer: Ref,
    plane_id: StrArg,
    *,
    title: StrArg,
    editable: BoolArg,
    cells: ListArg[dict],
) -> Nu:
    """Replace what the viewer draws: one plane and its cells, in order.

    A cell is ``{id, name, tpl, source}``. Every select is answered with one,
    even for something that is not a plane, or the viewer loads forever.
    """
    return write(viewer, "set_page", page_id=plane_id, title=title, editable=editable, blocks=cells)


def set_status(viewer: Ref, statuses: ListArg[dict]) -> Nu:
    """Patch what the viewer says about its cells.

    An entry is ``{section_id, state, error, started_at}``. A patch into the
    page already landed, so it follows a :func:`set_page`.
    """
    return write(viewer, "set_status", statuses=statuses)


# --- events: browser -> host --------------------------------------------------


def on_select(viewer: Ref) -> Changed:
    """The browser navigated to a plane. ``{page_id}``."""
    return event(viewer, "page.select")


def on_create_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, name, tpl, source, index}``. Browser minted id."""
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
