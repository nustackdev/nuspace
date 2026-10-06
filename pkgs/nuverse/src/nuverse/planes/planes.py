"""The ``planes`` Plane: every plane in the space, live.

Two cells, each redrawing once a second from one snapshot of the store: the
planes and cells per registered Plane that made them, and every plane.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["MADE_BY", "PLANE", "TABLE"]


MADE_BY = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


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


def draw():
    rows = ops.plane_rows().iter()
    tagged = rows.map(lambda p: nu.Dict.of(made=made(p), cells=cell_count(p["id"]))).to_list()
    return nustd.kv.Snapshot(nu.let(tagged, table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


TABLE = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def prop(p, name):
    return nu.Dict(p["props"])[name]


def cell_count(pid):
    return ops.cells(pid).len()


def draw():
    def row(p):
        system = nu.If(prop(p, "system"), "yes", "no")
        return nu.List.of(p["name"], prop(p, "made_by"), system, cell_count(p["id"]))

    table = nustd.ui.TableRef("planes").set(
        nu.Dict.of(
            columns=["Name", "Made by", "System", "Cells"],
            rows=ops.plane_rows().iter().map(row).to_list(),
        )
    )
    return nustd.kv.Snapshot(table, scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


PLANE = Plane(
    "planes",
    "Planes",
    icon="layers",
    description="Every plane by what made it, redrawn every second.",
    meta={"editable": True, "full_width": False},
    cells=(("made_by", MADE_BY), ("planes", TABLE)),
    group="System",
    backend="async",
)
