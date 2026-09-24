"""The ``planes`` app: a live page of every plane in the space.

Two cells, each redrawing once a second from one snapshot of the store: the
planes and cells per section, and every plane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import App

from ._live import live_page


if TYPE_CHECKING:
    import nu


__all__ = ["APP", "SECTIONS", "TABLE", "planes"]


SECTIONS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def section(p):
    meta = nu.Dict(p.get_item(nu.Str("meta"), nu.Dict.of()))
    return nu.If(p["system"], nu.Str("system"), nu.ToStr(meta.get_item(nu.Str("made_by"), "-")))


def cell_count(pid):
    return nu.Len(nu.list(nuspace.Space.planes[pid].cells.keys()))


def members(planes, s):
    return nu.Filter(nu.Iter(planes), nu.Eq(nu.DictAttrRef("p")["section"], s), key="p")


def draw():
    p, s = nu.DictAttrRef("p"), nu.StrAttrRef("s")
    planes = nu.ListAttrRef("planes")
    tagged = nu.Collect(
        nu.Map(ops.plane_rows(), nu.Dict.of(section=section(p), cells=cell_count(p["id"])), key="p")
    )
    row = nu.List.of(
        s, nu.Count(members(planes, s)), nu.Sum(nu.Map(members(planes, s), p["cells"], key="p"))
    )
    sections = nu.Unique(nu.Map(nu.Iter(planes), p["section"], key="p"))
    table = nustd.ui.TableRef("sections").set(
        nu.Dict.of(
            columns=["section", "planes", "cells"],
            rows=nu.Collect(nu.Map(sections, row, key="s")),
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


def made_by(p):
    return nu.Dict(p.get_item(nu.Str("meta"), nu.Dict.of())).get_item(nu.Str("made_by"), "")


def cell_count(pid):
    return nu.Len(nu.list(nuspace.Space.planes[pid].cells.keys()))


def draw():
    p = nu.DictAttrRef("p")
    row = nu.List.of(
        p["name"], made_by(p), nu.If(p["system"], "yes", "no"), cell_count(p["id"])
    )
    table = nustd.ui.TableRef("planes").set(
        nu.Dict.of(
            columns=["name", "made_by", "system", "cells"],
            rows=nu.Collect(nu.Map(ops.plane_rows(), row, key="p")),
        )
    )
    return nustd.kv.Snapshot(table, scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


def planes(plane_id: nu.StrArg | None = None, name: nu.StrArg = "") -> nu.Nu:
    """A live planes page. Yields its id."""
    return live_page("planes", plane_id, name, [("sections", SECTIONS), ("planes", TABLE)])


APP = App("planes", "Planes", planes, description="Every plane by section, redrawn every second.")
