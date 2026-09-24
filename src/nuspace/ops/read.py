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
from nuspace.shapes import ROOT, Space

from .utils import flag, fresh, text


__all__ = [
    "cell_exists",
    "cell_rows",
    "cells",
    "children",
    "parent",
    "plane_exists",
    "plane_rows",
    "planes",
    "prog",
]


def planes() -> nu.Nu:
    """Every plane id. Minted ids sort by creation, so this is creation order."""
    return nu.list(Space.planes.keys())


def plane_exists(plane_id: nu.StrArg) -> nu.Nu:
    """Whether a plane is stored under this id.

    ``contains``, since a container ref always materialises a view and
    ``exists()`` on a row answers True either way.
    """
    return Space.planes.contains(plane_id)


def cells(plane_id: nu.StrArg) -> nu.Nu:
    """A plane's cell ids, in order.

    ``order`` filtered to cells that exist, then any cell missing from
    ``order`` appended, so a cell that reached the store some other way is
    listed last rather than not at all.
    """
    plane = Space.planes[plane_id]
    item = fresh("cells")
    at = nu.AnyAttrRef(item)
    placed = nu.List(
        nu.Collect(nu.Filter(nu.list(plane.order), plane.cells.contains(at), key=item))
    )
    unplaced = nu.List(
        nu.Collect(
            nu.Filter(nu.list(plane.cells.keys()), nu.Not(plane.order.contains(at)), key=item)
        )
    )
    return placed + unplaced


def cell_exists(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Whether the plane holds a cell under this id."""
    return Space.planes[plane_id].cells.contains(cell_id)


def children(node_id: nu.StrArg = ROOT) -> nu.Nu:
    """A tree node's child plane ids, in order. ``[]`` for a node never written."""
    return nu.list(Space.tree[node_id].children)


def parent(plane_id: nu.StrArg) -> nu.Nu:
    """The tree node listing this plane: a plane id, or ``ROOT``.

    ``""`` for a plane no node lists, eg one written by hand or removed.
    """
    item = fresh("parent")
    at = nu.StrAttrRef(item)
    found = nu.First(
        nu.Filter(nu.list(Space.tree.keys()), Space.tree[at].children.contains(plane_id), key=item)
    )
    return nu.If(nu.IsEmpty(found), nu.Str(""), found)


def prog(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A cell's source, ``""`` where there is none."""
    return text(Space.planes[plane_id].cells[cell_id].prog)


def plane_rows() -> nu.Nu:
    """Every plane as ``id, name, props, meta, parent``. One read fills a sidebar.

    ``props`` is always whole, ``{system, ui, made_by}``, defaults filled in.
    """
    item = fresh("plane_rows")
    at = nu.StrAttrRef(item)
    plane = Space.planes[at]
    return nu.Collect(
        nu.Map(
            planes(),
            nu.Dict.of(
                id=at,
                name=text(plane.name),
                props=nu.Dict.of(
                    system=flag(plane.props.system, False),
                    ui=flag(plane.props.ui, False),
                    made_by=text(plane.props.made_by),
                ),
                meta=plane.meta.extract(),
                parent=parent(at),
            ),
            key=item,
        )
    )


def cell_rows(plane_id: nu.StrArg) -> nu.Nu:
    """A plane's cells as ``id, name, prog, meta``, in order. One read fills an editor."""
    item = fresh("cell_rows")
    at = nu.StrAttrRef(item)
    cell = Space.planes[plane_id].cells[at]
    return nu.Collect(
        nu.Map(
            cells(plane_id),
            nu.Dict.of(id=at, name=text(cell.name), prog=text(cell.prog), meta=cell.meta.extract()),
            key=item,
        )
    )
