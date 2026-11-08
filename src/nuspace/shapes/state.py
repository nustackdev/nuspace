"""State: the root of ``state.db``, what programs keep. Plain slots, plus Content.

Three scopes, cell, plane and space, each holding program slots directly,
then Content, the part of State with a kind::

    State
      cells[cell_id]                                       a cell's slots
      planes[plane_id]                                     a plane's, shared by its cells
      space                                                the space's
      content_cells[kind].cells[cell_id].entries[key]      items of a kind, at a cell
      content_planes[kind].planes[plane_id].entries[key]   at a plane
      content_space[kind].entries[key]                     at the space

Keyed by the ids in ``Space`` and nothing else: state belongs to the id, so
a removed cell or plane keeps its state and content, readable. Content goes
kind first, so a search reads one kind's subtree per scope and nothing
else. ``key`` is the item's content key, set by the program: its only
identity, unique within its kind at that place.

A scope and an item are empty Shapes: a program's own Shape sits on one
through ``with_parent``, typed, and nothing else shares its keys::

    Counter.value.with_parent(State.cells[cell_id])
    Text.value.with_parent(State.content_cells[kind].cells[cell_id].entries["title"])

Programs reach them through places (``nuspace.at``), which build exactly
these chains.

``State`` is also the store's tag, as :class:`~nuspace.shapes.space.Space`
is the other's.
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = [
    "CellScope",
    "Entries",
    "Entry",
    "KindCells",
    "KindPlanes",
    "PlaneScope",
    "SpaceScope",
    "State",
]


class CellScope(nu.Shape):
    """One cell's state, ``State.cells[id]``. No slots: a program's Shape sits on it."""


class PlaneScope(nu.Shape):
    """One plane's state, ``State.planes[id]``, shared by its cells. No slots of its own."""


class SpaceScope(nu.Shape):
    """The space's state, ``State.space``. No slots of its own."""


class Entry(nu.Shape):
    """One content item, ``...entries[key]``. No slots: its kind's Shape sits on it."""


class Entries(nu.Shape):
    """One place's items of one kind, by content key."""

    entries = nustd.kv.DictRef.slot(Entry)


class KindCells(nu.Shape):
    """One kind's items at cells: ``content_cells[kind].cells[cell_id]``."""

    cells = nustd.kv.DictRef.slot(Entries)


class KindPlanes(nu.Shape):
    """One kind's items at planes: ``content_planes[kind].planes[plane_id]``."""

    planes = nustd.kv.DictRef.slot(Entries)


class State(nu.Shape):
    """The root of ``state.db``, and its store's tag. Written by programs, through places."""

    cells = nustd.kv.DictRef.slot(CellScope)
    planes = nustd.kv.DictRef.slot(PlaneScope)
    space = nustd.kv.ShapeRef.slot(SpaceScope)
    content_cells = nustd.kv.DictRef.slot(KindCells)
    content_planes = nustd.kv.DictRef.slot(KindPlanes)
    content_space = nustd.kv.DictRef.slot(Entries)
