"""Structure reads: what planes and cells exist, where, and in what order.

Reads are bare: they carry no bracket, so they compose into any expression
and read inside whatever bracket encloses them (an op's own transaction
sees its pending writes). Evaluated alone, wrap one in
``nustd.kv.Snapshot(..., scope=Space)``.

Container reads go through ``nu.list`` or ``extract``: a lazy view dies
with the bracket that opened it.
"""

from __future__ import annotations

import nu
from nuspace.shapes import Space


__all__ = [
    "cell_exists",
    "cell_named",
    "cell_plane",
    "cell_rows",
    "cells",
    "children",
    "parent",
    "plane_exists",
    "plane_rows",
    "plane_title",
    "planes",
    "prog",
]


def planes() -> nu.List:
    """Every plane id. Minted ids sort by creation, so this is creation order."""
    return nu.list(Space.planes.keys())


def plane_exists(plane_id: nu.StrArg) -> nu.Bool:
    """Whether a plane is stored under this id.

    ``contains``, since a container ref always materialises a view and
    ``exists()`` on a row answers True either way.
    """
    return Space.planes.contains(plane_id)


def plane_title(plane_id: nu.StrArg) -> nu.Str:
    """What to call a plane: its name, its id where the name is unwritten or ``""``. Bare read."""
    name = Space.planes[plane_id].name.fallback("")
    return nu.Str(nu.If(name == "", plane_id, name))


def cells(plane_id: nu.StrArg) -> nu.List:
    """A plane's cell ids, in order. ``[]`` for a plane never written."""
    return nu.list(Space.planes[plane_id].cells)


def cell_exists(cell_id: nu.StrArg) -> nu.Bool:
    """Whether a cell is stored under this id."""
    return Space.cells.contains(cell_id)


def cell_named(plane_id: nu.StrArg, name: nu.StrArg) -> nu.Str:
    """The id of the first cell on a plane called ``name``, ``""`` for none. Names are not unique."""
    named = (
        cells(plane_id).iter().filter(lambda c: Space.cells[nu.Str(c)].name.fallback("") == name)
    )
    return nu.str(nu.First(named)).fallback("")


def cell_plane(cell_id: nu.StrArg) -> nu.Str:
    """The id of the plane a cell is on, ``""`` for no such cell."""
    return Space.cells[cell_id].plane.fallback("")


def children(plane_id: nu.StrArg = "") -> nu.List:
    """A plane's child plane ids, in order, the top level ones for ``""``.

    ``[]`` for a plane never written.
    """
    under = nu.list(Space.planes[plane_id].children)
    return nu.List(nu.If(nu.Str(plane_id) == "", nu.list(Space.top), under))


def parent(plane_id: nu.StrArg) -> nu.Str:
    """The plane listing this one, ``""`` at the top level and for no such plane. One read."""
    return Space.planes[plane_id].parent.fallback("")


def prog(cell_id: nu.StrArg) -> nu.Str:
    """A cell's source, ``""`` where there is none."""
    return nu.str(Space.cells[cell_id].prog).fallback("")


def plane_rows() -> nu.List:
    """Every plane as ``id, name, props, meta, parent``. One read fills a sidebar.

    A few reads per plane, ``parent`` included: ``""`` for a top level one.

    ``props`` is always whole, ``{system, ui, made_by, backend}``, defaults
    filled in. ``backend`` is ``""`` for a plane that names none.
    """

    def row(at: nu.Attr) -> nu.Dict:
        plane = Space.planes[nu.Str(at)]
        return nu.Dict.of(
            id=at,
            name=plane.name.fallback(""),
            props=nu.Dict.of(
                system=plane.props.system.fallback(False),
                ui=plane.props.ui.fallback(False),
                made_by=plane.props.made_by.fallback(""),
                backend=plane.props.backend.fallback(""),
            ),
            meta=plane.meta.extract(),
            parent=plane.parent.fallback(""),
        )

    return planes().iter().map(row).to_list()


def cell_rows(plane_id: nu.StrArg) -> nu.List:
    """A plane's cells as ``id, name, prog, props, meta``, in order. One read fills an editor.

    ``props`` is always whole, ``{made_by, has_ui}``, defaults filled in.
    ``has_ui`` reads True where it was never worked out: maybe it draws.
    """

    def row(at: nu.Attr) -> nu.Dict:
        cell = Space.cells[nu.Str(at)]
        return nu.Dict.of(
            id=at,
            name=cell.name.fallback(""),
            prog=nu.str(cell.prog).fallback(""),
            props=nu.Dict.of(
                made_by=cell.props.made_by.fallback(""), has_ui=cell.props.has_ui.fallback(True)
            ),
            meta=cell.meta.extract(),
        )

    return cells(plane_id).iter().map(row).to_list()
