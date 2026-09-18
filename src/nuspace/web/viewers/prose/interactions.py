"""Everything the prose surface says and hears, in the browser's own words.

Two halves, and every name here is the spelling on the wire rather than the
one in the model. A Plane is a ``page`` to the browser and a Cell is a
``section``, because the browser was written against those words and moving it
to the model's is a deliberate move of its own, made later.

- **Events**, browser to server. One subscription per op, each on a path of its
  own under ``<surface>.ops.``. The path is the discrimination, so a driver
  binds one arm per op instead of switching on a string in a payload, and a
  browser that spells an op wrong notifies into a path nobody listens on
  rather than into somebody else's handler.
- **Writes**, server to browser. Three of them, all on the surface's own path
  and all tagged with an ``op`` key, because the browser registers one handler
  per node and a write to a path with no handler is dropped. That is why these
  cannot each take a path of their own the way the events do.

Nothing here reads or writes a store. What an event means is
:mod:`nuspace.ops`, and which op is wired to which arm is
:mod:`nuspace.web.viewers.prose.driver`.

**Ids are minted by the browser.** ``page.create`` and ``section.create`` carry
the id of the thing being made, so a create is a pure function of its event:
re-running an arm rewrites one row instead of adding a second, and the browser
routes to what it just made without waiting to be told its name.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu, StrArg
    from nustd.ui.core import Changed, Ref


__all__ = [
    "TPL_PROGRAM",
    "TPL_TEXT",
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
    "set_page",
    "set_status",
    "set_tree",
]


#: A Cell the person writes prose into. The browser gives it a document
#: surface with block boundaries; anything else gets a source editor.
TPL_TEXT = "text"

#: A Cell the person writes a program into. Every value that is not
#: :data:`TPL_TEXT` reads as this one on the other side.
TPL_PROGRAM = "program"


# --- writes: server -> browser ----------------------------------------------


def set_tree(surface: Ref, planes: ListArg[dict]) -> Nu:
    """Replace the rail: every Plane the surface lists, flat.

    A row is ``{id, title, parent, children}``, and exactly one of them has to
    name itself as its own parent or the browser finds no root and the rail
    stays a row of skeletons forever.
    """
    return write(surface, "set_tree", pages=planes)


def set_page(
    surface: Ref,
    plane_id: StrArg,
    *,
    title: StrArg,
    parent: StrArg,
    children: ListArg[str],
    cells: ListArg[dict],
) -> Nu:
    """Replace the canvas: one Plane, and its Cells in order.

    A Cell is ``{id, name, tpl, source}`` and order is list position. Until one
    of these lands the canvas says it is loading, so every select is answered
    with one even when it names something that is not a Plane.
    """
    return write(
        surface,
        "set_page",
        page_id=plane_id,
        title=title,
        parent=parent,
        children=children,
        blocks=cells,
    )


def set_status(surface: Ref, statuses: ListArg[dict]) -> Nu:
    """Patch what the canvas says about the Cells it is showing.

    An entry is ``{section_id, state, error, started_at}`` and a Cell the batch
    does not name keeps whatever it was showing. A patch into whatever the
    canvas already holds, so it does nothing at all until a :func:`set_page`
    has landed, and the two have to be sent in that order.
    """
    return write(surface, "set_status", statuses=statuses)


# --- events: browser -> server ----------------------------------------------


def on_select(surface: Ref) -> Changed:
    """The browser navigated to a Plane. ``{page_id}``."""
    return event(surface, "page.select")


def on_create_plane(surface: Ref) -> Changed:
    """``{page_id, parent_id, title}``. The browser minted ``page_id``."""
    return event(surface, "page.create")


def on_rename_plane(surface: Ref) -> Changed:
    """``{page_id, title}``."""
    return event(surface, "page.rename")


def on_delete_plane(surface: Ref) -> Changed:
    """``{page_id}``."""
    return event(surface, "page.delete")


def on_move_plane(surface: Ref) -> Changed:
    """``{page_id, parent_id, index}``. Reparent, landing at ``index``."""
    return event(surface, "page.move")


def on_reorder_planes(surface: Ref) -> Changed:
    """``{parent_id, page_ids}``. One parent's children, in the new order."""
    return event(surface, "page.reorder")


def on_create_cell(surface: Ref) -> Changed:
    """``{page_id, section_id, name, tpl, source, index}``. Browser-minted id."""
    return event(surface, "section.create")


def on_update_cell(surface: Ref) -> Changed:
    """``{page_id, section_id, source}``. Replaces the program, nothing else."""
    return event(surface, "section.update")


def on_delete_cell(surface: Ref) -> Changed:
    """``{page_id, section_id}``."""
    return event(surface, "section.delete")


def on_move_cell(surface: Ref) -> Changed:
    """``{page_id, section_id, to_page_id, index}``. Keeps the Cell's id."""
    return event(surface, "section.move")


def on_reorder_cells(surface: Ref) -> Changed:
    """``{page_id, section_ids}``. One Plane's Cells, in the new order."""
    return event(surface, "section.reorder")
