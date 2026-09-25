"""The ``cell_lens`` snippet: a lens on one cell of this plane, picked from a dropdown.

The dropdown lists the plane's cells in order and follows cells being added
or removed. Picking one restarts the lens on it. Edit ``SHAPE`` and
``PREFIX`` inside ``out`` to browse something else of the picked cell.
"""

from __future__ import annotations

from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


SOURCE = """\
import nu
import nustd.kv
import nustd.ui
import nustd.ui.lens
import nuspace
from nuspace import ops


def out(plane, cell):
    picked = nu.StrAttrRef("picked")

    # SHAPE is a shape class: what the lens expects to find.
    # PREFIX is a ref: where in the store that shape lives. Here, the picked cell.
    SHAPE = nuspace.shapes.Cell
    PREFIX = nuspace.Space.planes[plane].cells[picked]

    pick = nustd.ui.SelectRef("cell")
    lens = nustd.ui.lens.LensRef("lens")

    def read(term):
        return nustd.kv.Snapshot(term, scope=nuspace.Space)

    # The plane's cells in order, labelled by name, or by id when unnamed.
    row = nu.DictAttrRef("row")
    label = nu.If(nu.Ne(row["name"], ""), row["name"], row["id"])
    option = nu.Dict.of(value=row["id"], label=label)
    options = read(nu.Collect(nu.Map(ops.cell_rows(plane), option, key="row")))
    # The first cell that is not this one, or this one when it is alone.
    others = nu.First(nu.Filter(ops.cells(plane), nu.Ne(nu.StrAttrRef("id"), cell), key="id"))
    first = read(nu.If(nu.IsEmpty(others), nu.Str(cell), others))

    # browse never finishes: each pick cancels it and starts it on the new cell.
    lens_on_pick = nu.ReactLatest(
        pick.on_change(),
        nu.Let("picked", nu.Str(pick), nustd.ui.lens.browse(lens, SHAPE, prefix=PREFIX)),
        initial=True,
    )
    # Cells added or removed on the plane: list them again.
    cells_moved = nu.ReactForever(
        read(nuspace.Space.planes[plane].cells.on_children_change()),
        pick.set_options(options),
    )
    return (
        pick.set_options(options)
        >> pick.set(first)
        >> nu.ParallelAsync(lens_on_pick, cells_moved)
    )
"""

SNIPPET = Snippet("cell_lens", "Cell lens", SOURCE)
