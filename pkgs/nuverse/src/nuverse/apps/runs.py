"""The ``runs`` app: a live page of what the kernel is running and what just ended.

Three cells, each redrawing once a second from one snapshot of the store:
the counts, the live runs, and the last finished ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import App

from ._live import live_page


if TYPE_CHECKING:
    import nu


__all__ = ["APP", "COUNTS", "FINISHED", "LIVE", "runs"]


COUNTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def count(runs, exit):
    return nu.Count(nu.Filter(nu.Iter(runs), nu.Eq(nu.DictAttrRef("r")["exit"], exit), key="r"))


def tile(name, value):
    return nustd.ui.StatRef(name).set(nu.ToStr(value), label=name)


def draw():
    runs = nu.ListAttrRef("runs")
    tiles = (
        tile("live", nu.Len(ops.live_runs()))
        >> tile("ok", count(runs, "ok"))
        >> tile("failed", count(runs, "failed"))
        >> tile("killed", count(runs, "killed"))
    )
    return nustd.kv.Snapshot(nu.Let("runs", ops.runs(), tiles), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


LIVE = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops


def plane_name(pid):
    name = nuspace.Space.planes[pid].name
    return nu.If(name.exists(), nu.ToStr(name), pid)


def age(t):
    now = nu.FloatAttrRef("now")
    return nu.If(nu.Is(t, None), nu.Str(""), nu.Format(now - t, ".0f") + nu.Str("s"))


def draw():
    r = nu.DictAttrRef("r")
    live = nu.Filter(nu.Iter(ops.runs()), nu.Ne(r["status"], "dead"), key="r")
    row = nu.List.of(
        plane_name(r["plane"]), r["cell"], r["worker"], r["by"], r["status"], age(r["started"])
    )
    table = nustd.ui.TableRef("live runs").set(
        nu.Dict.of(
            columns=["plane", "cell", "worker", "by", "status", "age"],
            rows=nu.Collect(nu.Map(live, row, key="r")),
        )
    )
    return nustd.kv.Snapshot(nu.Let("now", nustd.time.time(), table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


FINISHED = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops


def plane_name(pid):
    name = nuspace.Space.planes[pid].name
    return nu.If(name.exists(), nu.ToStr(name), pid)


def ago(t):
    now = nu.FloatAttrRef("now")
    return nu.If(nu.Is(t, None), nu.Str(""), nu.Format(now - t, ".0f") + nu.Str("s ago"))


def draw():
    r = nu.DictAttrRef("r")
    dead = nu.Filter(nu.Iter(ops.runs(status="dead")), nu.Not(nu.Is(r["ended"], None)), key="r")
    newest = nu.List(nu.Collect(nu.SortBy(dead, r["ended"], reverse=True, item="r")))[0:20]
    row = nu.List.of(
        plane_name(r["plane"]), r["cell"], r["exit"], nu.Str(r["error"])[0:80], ago(r["ended"])
    )
    table = nustd.ui.TableRef("finished runs").set(
        nu.Dict.of(
            columns=["plane", "cell", "exit", "error", "ended"],
            rows=nu.Collect(nu.Map(nu.Iter(newest), row, key="r")),
        )
    )
    return nustd.kv.Snapshot(nu.Let("now", nustd.time.time(), table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


def runs(plane_id: nu.StrArg | None = None, name: nu.StrArg = "") -> nu.Nu:
    """A live runs page. Yields its id."""
    cells = [("counts", COUNTS), ("live", LIVE), ("finished", FINISHED)]
    return live_page("runs", plane_id, name, cells)


APP = App("runs", "Runs", runs, description="Live and recent runs, redrawn every second.")
