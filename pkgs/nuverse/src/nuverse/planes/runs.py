"""The ``runs`` Plane: what the kernel is running now, live.

Three cells, each redrawing once a second from one snapshot of the store:
the counts, the live plane runs, and their live cell runs. Everything is
read off the live indexes, so it costs what is running, never history.
"""

from __future__ import annotations

import nu
from nuspace import Plane


__all__ = ["CELLS", "COUNTS", "LIVE", "PLANE", "age"]


def age(now: nu.Nu, t: nu.Nu, unknown: str = "") -> nu.Nu:
    """How long since ``t``, eg ``12s``, ``unknown`` while ``t`` is None. For cell sources to import."""
    return nu.If(nu.Is(t, None), unknown, nu.format(nu.Float(now) - t, ".0f") + "s")


COUNTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def tile(name, label, value):
    return nustd.ui.StatRef(name).set(nu.str(value), label=label)


def tiles(runs):
    cells = nu.Sum(nu.Map(nu.Iter(runs), lambda r: nu.List(r["cells_running"]).len()))
    return (
        tile("runs", "Live runs", nu.List(runs).len())
        >> tile("cells", "Live cells", cells)
        >> tile("workers", "Workers up", ops.workers().len())
    )


def draw():
    return nustd.kv.Snapshot(nu.let(ops.runs(), tiles), scope=nuspace.Space)


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
from nuverse.planes.runs import age


def table(now):
    def row(r):
        return nu.List.of(
            nuspace.Space.planes[r["plane"]].name.fallback(r["plane"]),
            r["backend"],
            r["by"],
            nu.List(r["cells_running"]).len(),
            nu.List(r["workers"]).len(),
            age(now, r["started_at"]),
        )

    return nustd.ui.TableRef("live runs").set(
        nu.Dict.of(
            columns=["Plane", "Backend", "By", "Cells", "Workers", "Age"],
            rows=ops.runs().iter().map(row).to_list(),
        )
    )


def draw():
    return nustd.kv.Snapshot(nu.let(nustd.time.time(), table), scope=nuspace.Space)


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
from nuverse.planes.runs import age


def table(now):
    def row(r, c):
        pid, cid = nu.str(r["plane"]), nu.str(c["cell"])
        plane = nuspace.Space.planes[pid]
        return nu.List.of(
            plane.name.fallback(pid),
            nuspace.Space.cells[cid].name.fallback(cid),
            c["by"],
            c["version"],
            c["worker"],
            age(now, c["started_at"], "starting"),
        )

    def cells(r):
        live = ops.cell_runs(nu.str(r["id"]), live=True).iter()
        return live.map(lambda c: row(r, c)).to_list()

    rows = ops.runs().iter().map(cells)
    return nustd.ui.TableRef("live cells").set(
        nu.Dict.of(
            columns=["Plane", "Cell", "By", "Version", "Worker", "Age"],
            rows=nu.Collect(nu.Flatten(rows)),
        )
    )


def draw():
    return nustd.kv.Snapshot(nu.let(nustd.time.time(), table), scope=nuspace.Space)


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
