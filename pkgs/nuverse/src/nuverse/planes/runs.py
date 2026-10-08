"""The ``runs`` Plane: what the kernel is running now, live.

Three cells, each drawn again when what is live changes, and only when what
it shows did: the counts, the live plane runs, and their live cell runs.
Everything is read off the live indexes, so it costs what is running, never
history. Ages move with the clock, so the tables are read again every
minute too.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace import Plane


__all__ = ["CELLS", "COUNTS", "LIVE", "PLANE", "age", "lives"]


def age(now: nu.Nu, t: nu.Nu, unknown: str = "") -> nu.Nu:
    """How long since ``t`` in minutes, eg ``12m``, ``unknown`` while ``t`` is None. For cell sources to import."""
    m = nu.int(nu.Float(now) - t) // 60
    spelled = nu.If(
        m < 1, "<1m", nu.If(m < 60, nu.str(m) + "m", nu.str(m // 60) + "h " + nu.str(m % 60) + "m")
    )
    return nu.If(nu.Is(t, None), unknown, spelled)


def lives() -> list[nu.Nu]:
    """What says what is live moved: a plane run, a cell run, a cell run starting, a worker.

    Fresh subscriptions on every call. For cell sources to import.
    """
    kernel = nuspace.Space.kernel
    return [
        kernel.running.on_children_change(),
        kernel.runs.on_descendants_change("*", "cells_running", "*"),
        kernel.runs.on_descendants_change("*", "cells", "*", "started_at"),
        kernel.workers_running.on_children_change(),
    ]


COUNTS = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws
from nuverse.planes.runs import lives


def tile(name, label, value):
    return nustd.ui.StatRef(name).set(nu.str(value), label=label)


def counts():
    kernel = nuspace.Space.kernel
    running = nu.list(kernel.running)
    cells = nu.Sum(nu.Map(nu.Iter(running), lambda r: kernel.runs[nu.Str(r)].cells_running.len()))
    return nu.List.of(running.len(), cells, kernel.workers_running.len())


def tiles(n):
    return (
        tile("runs", "Live runs", n[0])
        >> tile("cells", "Live cells", n[1])
        >> tile("workers", "Workers up", n[2])
    )


def draw():
    return nu.let(ops.snapshot(counts()), tiles)


out = redraws(lives(), counts(), tiles)
"""


LIVE = """\
import nu
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws
from nuverse.planes.runs import age, lives


def rows():
    now = nustd.time.time()

    def row(r):
        return nu.List.of(
            nuspace.Space.planes[r["plane"]].name.fallback(r["plane"]),
            r["backend"],
            r["by"],
            nu.List(r["cells_running"]).len(),
            nu.List(r["workers"]).len(),
            age(now, r["started_at"]),
        )

    return ops.runs().iter().map(row).to_list()


def table(shown):
    columns = ["Plane", "Backend", "By", "Cells", "Workers", "Age"]
    return nustd.ui.TableRef("live runs").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(ops.snapshot(rows()), table)


out = redraws(lives(), rows(), table, every=60.0)
"""


CELLS = """\
import nu
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws
from nuverse.planes.runs import age, lives


def rows():
    now = nustd.time.time()

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

    return nu.List(nu.Collect(nu.Flatten(ops.runs().iter().map(cells))))


def table(shown):
    columns = ["Plane", "Cell", "By", "Version", "Worker", "Age"]
    return nustd.ui.TableRef("live cells").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(ops.snapshot(rows()), table)


out = redraws(lives(), rows(), table, every=60.0)
"""


PLANE = Plane(
    "runs",
    "Runs",
    icon="activity",
    description="Live plane runs and their cells, kept live.",
    meta={"editable": True, "full_width": False},
    cells=(("counts", COUNTS), ("live", LIVE), ("cells", CELLS)),
    group="System",
    backend="async",
)
