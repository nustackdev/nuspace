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
    made_by = nu.ToStr(props["made_by"])
    return nu.If(
        props["system"], nu.Str("system"), nu.If(nu.Eq(made_by, ""), nu.Str("-"), made_by)
    )


def cell_count(pid):
    return nu.Len(nu.list(nuspace.Space.planes[pid].cells.keys()))


def members(planes, m):
    return nu.Filter(nu.Iter(planes), nu.Eq(nu.DictAttrRef("p")["made"], m), key="p")


def draw():
    p, m = nu.DictAttrRef("p"), nu.StrAttrRef("m")
    planes = nu.ListAttrRef("planes")
    tagged = nu.Collect(
        nu.Map(ops.plane_rows(), nu.Dict.of(made=made(p), cells=cell_count(p["id"])), key="p")
    )
    row = nu.List.of(
        m, nu.Count(members(planes, m)), nu.Sum(nu.Map(members(planes, m), p["cells"], key="p"))
    )
    makers = nu.Unique(nu.Map(nu.Iter(planes), p["made"], key="p"))
    table = nustd.ui.TableRef("made by").set(
        nu.Dict.of(
            columns=["Made by", "Planes", "Cells"],
            rows=nu.Collect(nu.Map(makers, row, key="m")),
        )
    )
    return nustd.kv.Snapshot(nu.Let("planes", tagged, table), scope=nuspace.Space)


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
    return nu.Len(nu.list(nuspace.Space.planes[pid].cells.keys()))


def draw():
    p = nu.DictAttrRef("p")
    row = nu.List.of(
        p["name"], prop(p, "made_by"), nu.If(prop(p, "system"), "yes", "no"), cell_count(p["id"])
    )
    table = nustd.ui.TableRef("planes").set(
        nu.Dict.of(
            columns=["Name", "Made by", "System", "Cells"],
            rows=nu.Collect(nu.Map(ops.plane_rows(), row, key="p")),
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
)
