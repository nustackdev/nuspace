"""Everything the Viewer says and hears, in the browser's own words.

Two halves, and every name here is the spelling on the wire rather than the
one in the model. A Plane is a ``page`` to the browser and a Cell is a
``section``, because the browser was written against those words and moving it
to the model's is a deliberate move of its own, made later.

- **Events**, browser to server. One subscription per op, each on a path of its
  own under ``<viewer>.ops.``. The path is the discrimination, so a driver
  binds one arm per op instead of switching on a string in a payload, and a
  browser that spells an op wrong notifies into a path nobody listens on
  rather than into somebody else's handler.
- **Writes**, server to browser. Two of them, both on the Viewer's own path and
  both tagged with an ``op`` key, because the browser registers one handler
  per node and a write to a path with no handler is dropped. That is why these
  cannot each take a path of their own the way the events do.

Nothing here reads or writes a store. What an event means is
:mod:`nuspace.ops`, and which op is wired to which arm is
:mod:`nuspace.web.viewer.driver`.

**Ids are minted by the browser.** ``section.create`` carries the id of the
Cell being made, so a create is a pure function of its event: re-running an arm
rewrites one row instead of adding a second.

``page.select`` is the Viewer's and not the sidebar's. The sidebar moves the
browser's URL, and what the URL now names is a fact about what the Viewer has
open.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import BoolArg, ListArg, Nu, StrArg
    from nustd.ui.core import Changed, Ref


__all__ = [
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


#: A Cell the person writes prose into. The browser gives it a document
#: surface with block boundaries; anything else gets a source editor.
TPL_TEXT = "text"

#: A Cell the person writes a program into. Every value that is not
#: :data:`TPL_TEXT` reads as this one on the other side.
TPL_PROGRAM = "program"


# --- writes: server -> browser ----------------------------------------------


def set_page(
    viewer: Ref,
    plane_id: StrArg,
    *,
    title: StrArg,
    editable: BoolArg,
    cells: ListArg[dict],
) -> Nu:
    """Replace what the Viewer draws: one Plane, and its Cells in order.

    A Cell is ``{id, name, tpl, source}`` and order is list position. Until one
    of these lands the Viewer says it is loading, so every select is answered
    with one even when it names something that is not a Plane.

    ``editable`` rides along because it is the Plane's own prop and changes
    when the open Plane changes. It is what the browser gates the controls a
    document has on, and the Viewer never decides it.
    """
    return write(
        viewer,
        "set_page",
        page_id=plane_id,
        title=title,
        editable=editable,
        blocks=cells,
    )


def set_status(viewer: Ref, statuses: ListArg[dict]) -> Nu:
    """Patch what the Viewer says about the Cells it is showing.

    An entry is ``{section_id, state, error, started_at}`` and a Cell the batch
    does not name keeps whatever it was showing. A patch into whatever the
    Viewer already holds, so it does nothing at all until a :func:`set_page`
    has landed, and the two have to be sent in that order.
    """
    return write(viewer, "set_status", statuses=statuses)


# --- events: browser -> server ----------------------------------------------


def on_select(viewer: Ref) -> Changed:
    """The browser navigated to a Plane. ``{page_id}``."""
    return event(viewer, "page.select")


def on_create_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, name, tpl, source, index}``. Browser-minted id."""
    return event(viewer, "section.create")


def on_update_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, source}``. Replaces the program, nothing else."""
    return event(viewer, "section.update")


def on_delete_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id}``."""
    return event(viewer, "section.delete")


def on_move_cell(viewer: Ref) -> Changed:
    """``{page_id, section_id, to_page_id, index}``. Keeps the Cell's id."""
    return event(viewer, "section.move")


def on_reorder_cells(viewer: Ref) -> Changed:
    """``{page_id, section_ids}``. One Plane's Cells, in the new order."""
    return event(viewer, "section.reorder")
