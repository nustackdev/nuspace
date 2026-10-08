"""The ``planes`` Plane: every plane in the space, live.

Two cells, each drawn again when a plane comes, goes, is renamed or has its
cells written, and only when what it shows changed: the planes and cells per
registered Plane that made them, and every plane.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["MADE_BY", "PLANE", "TABLE"]


MADE_BY = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws


def made(p):
    props = nu.Dict(p["props"])
    made_by = nu.str(props["made_by"])
    return nu.If(props["system"], "system", nu.If(made_by == "", "-", made_by))


def cell_count(pid):
    return ops.cells(pid).len()


def members(planes, m):
    return nu.Filter(nu.Iter(planes), lambda p: p["made"] == m)


def table(planes):
    def row(at):
        m = nu.Str(at)
        cells = nu.Sum(nu.Map(members(planes, m), lambda p: p["cells"]))
        return nu.List.of(m, nu.Count(members(planes, m)), cells)

    makers = nu.Unique(nu.Map(nu.Iter(planes), lambda p: p["made"]))
    return nustd.ui.TableRef("made by").set(
        nu.Dict.of(
            columns=["Made by", "Planes", "Cells"],
            rows=nu.Collect(nu.Map(makers, row)),
        )
    )


def tagged():
    rows = ops.plane_rows().iter()
    return rows.map(lambda p: nu.Dict.of(made=made(p), cells=cell_count(p["id"]))).to_list()


def draw():
    return nu.let(ops.snapshot(tagged()), table)


# A plane's own fields: made, removed, renamed, its cells written (version).
out = redraws([nuspace.Space.planes.on_descendants_change("*", "*")], tagged(), table)
"""


TABLE = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws


def prop(p, name):
    return nu.Dict(p["props"])[name]


def cell_count(pid):
    return ops.cells(pid).len()


def rows():
    def row(p):
        system = nu.If(prop(p, "system"), "yes", "no")
        return nu.List.of(p["name"], prop(p, "made_by"), system, cell_count(p["id"]))

    return ops.plane_rows().iter().map(row).to_list()


def table(shown):
    columns = ["Name", "Made by", "System", "Cells"]
    return nustd.ui.TableRef("planes").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(ops.snapshot(rows()), table)


# A plane's own fields: made, removed, renamed, its cells written (version).
out = redraws([nuspace.Space.planes.on_descendants_change("*", "*")], rows(), table)
"""


PLANE = Plane(
    "planes",
    "Planes",
    icon="layers",
    description="Every plane by what made it, kept live.",
    meta={"editable": True, "full_width": False},
    cells=(("made_by", MADE_BY), ("planes", TABLE)),
    group="System",
    backend="async",
)
