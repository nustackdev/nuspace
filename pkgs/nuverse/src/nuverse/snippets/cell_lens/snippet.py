"""A lens on one cell of its plane, picked from a dropdown.

The dropdown lists the plane's cells in order and follows cells being added
or removed. Picking one restarts the lens on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.kv
import nustd.ui
import nustd.ui.lens
from nuspace import ops


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["out"]


def out(plane: nu.StrArg, cell: nu.StrArg, shape: type, at: Callable[[nu.Nu], nu.Ref]) -> nu.Nu:
    """The dropdown and the lens on the picked cell, for as long as the cell runs.

    Args:
        plane: The plane whose cells it lists.
        cell: The cell running it, picked first when it is alone.
        shape: A shape class: what the lens expects to find.
        at: The ref that shape lives at, given the picked cell's id.
    """
    pick = nustd.ui.SelectRef("cell")
    lens = nustd.ui.lens.LensRef("lens")

    def read(term: nu.Nu) -> nu.Nu:
        return nustd.kv.Snapshot(term, scope=nuspace.Space)

    # The plane's cells in order, labelled by name, or by id when unnamed.
    def option(row: nu.Nu) -> nu.Nu:
        label = nu.If(row["name"] != "", row["name"], row["id"])
        return nu.Dict.of(value=row["id"], label=label)

    options = read(ops.cell_rows(plane).iter().map(option).to_list())
    # The first cell that is not this one, or this one when it is alone.
    others = ops.cells(plane).iter().filter(lambda c: c != cell).first()
    first = read(nu.Str(others).fallback(cell))

    # browse never finishes: each pick cancels it and starts it on the new cell.
    browse = nu.let(
        nu.Str(pick), lambda picked: nustd.ui.lens.browse(lens, shape, prefix=at(nu.Str(picked)))
    )
    lens_on_pick = nu.ReactLatest(pick.on_change(), browse, initial=True)
    # Cells added or removed on the plane: list them again.
    cells_moved = nu.ReactForever(
        read(nuspace.Space.planes[plane].cells.on_children_change()),
        pick.set_options(options),
    )
    return (
        pick.set_options(options) >> pick.set(first) >> nu.ParallelAsync(lens_on_pick, cells_moved)
    )
