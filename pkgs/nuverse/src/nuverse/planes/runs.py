"""The ``runs`` Plane: what the kernel is running now, live.

Three cells, each redrawing once a second from one snapshot of the store:
the counts, the live plane runs, and their live cell runs. Everything is
read off the live indexes, so it costs what is running, never history.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["CELLS", "COUNTS", "LIVE", "PLANE"]


COUNTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def tile(name, label, value):
    return nustd.ui.StatRef(name).set(nu.ToStr(value), label=label)


def draw():
    runs = nu.ListAttrRef("runs")
    r = nu.DictAttrRef("r")
    cells = nu.Sum(nu.Map(nu.Iter(runs), nu.Len(nu.List(r["cells_running"])), key="r"))
    tiles = (
        tile("runs", "Live runs", nu.Len(runs))
        >> tile("cells", "Live cells", cells)
        >> tile("workers", "Workers up", nu.Len(ops.workers()))
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
    row = nu.List.of(
        plane_name(r["plane"]),
        r["backend"],
        r["by"],
        nu.Len(nu.List(r["cells_running"])),
        nu.Len(nu.List(r["workers"])),
        age(r["started_at"]),
    )
    table = nustd.ui.TableRef("live runs").set(
        nu.Dict.of(
            columns=["Plane", "Backend", "By", "Cells", "Workers", "Age"],
            rows=nu.Collect(nu.Map(nu.Iter(ops.runs()), row, key="r")),
        )
    )
    return nustd.kv.Snapshot(nu.Let("now", nustd.time.time(), table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


CELLS = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops


def name(ref, fallback):
    return nu.If(ref.exists(), nu.ToStr(ref), fallback)


def age(t):
    now = nu.FloatAttrRef("now")
    return nu.If(nu.Is(t, None), nu.Str("starting"), nu.Format(now - t, ".0f") + nu.Str("s"))


def draw():
    r, c = nu.DictAttrRef("r"), nu.DictAttrRef("c")
    plane = nuspace.Space.planes[nu.ToStr(r["plane"])]
    row = nu.List.of(
        name(plane.name, nu.ToStr(r["plane"])),
        name(plane.cells[nu.ToStr(c["cell"])].name, nu.ToStr(c["cell"])),
        c["by"],
        c["version"],
        c["worker"],
        age(c["started_at"]),
    )
    rows = nu.Map(
        nu.Iter(ops.runs()),
        nu.Collect(nu.Map(nu.Iter(ops.cell_runs(nu.ToStr(r["id"]), live=True)), row, key="c")),
        key="r",
    )
    table = nustd.ui.TableRef("live cells").set(
        nu.Dict.of(
            columns=["Plane", "Cell", "By", "Version", "Worker", "Age"],
            rows=nu.Collect(nu.Flatten(rows)),
        )
    )
    return nustd.kv.Snapshot(nu.Let("now", nustd.time.time(), table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


PLANE = Plane(
    "runs",
    "Runs",
    icon="activity",
    description="Live plane runs and their cells, redrawn every second.",
    meta={"editable": True, "full_width": False},
    cells=(("counts", COUNTS), ("live", LIVE), ("cells", CELLS)),
    backend="async",
)
