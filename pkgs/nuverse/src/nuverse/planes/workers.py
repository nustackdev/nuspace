"""The ``workers`` Plane: the workers the backends hold, live.

Two cells, each redrawing once a second from one snapshot of the store: the
counts per backend, and every live worker with the run it serves. Read off
``workers_running``, so it costs what is up, never history.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["COUNTS", "PLANE", "TABLE"]


COUNTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def count(workers, backend):
    return nu.Count(nu.Filter(nu.Iter(workers), lambda w: w["backend"] == backend))


def tiles(workers):
    up = nustd.ui.StatRef("up").set(nu.str(nu.List(workers).len()), label="Up")
    return up >> nu.Sequential(
        *[
            nustd.ui.StatRef(backend).set(nu.str(count(workers, backend)), label=backend)
            for backend in ("async", "mp")
        ]
    )


def draw():
    return nustd.kv.Snapshot(nu.let(ops.workers(), tiles), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


TABLE = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuverse.planes.runs import age


def cells_on(w):
    # The run's live cell runs placed on this worker: a walk of what is live.
    live = ops.cell_runs(nu.str(w["run"]), live=True).iter()
    return nu.Count(live.filter(lambda c: c["worker"] == w["id"]))


def table(now):
    def row(w):
        name = nuspace.Space.planes[w["plane"]].name.fallback(w["plane"])
        return nu.List.of(
            w["id"], w["backend"], name, w["run"], cells_on(w), age(now, w["started_at"])
        )

    newest = nu.List(nu.Collect(nu.Reversed(ops.workers())))
    return nustd.ui.TableRef("workers").set(
        nu.Dict.of(
            columns=["ID", "Backend", "Plane", "Run", "Cells", "Age"],
            rows=newest.iter().map(row).to_list(),
        )
    )


def draw():
    return nustd.kv.Snapshot(nu.let(nustd.time.time(), table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


PLANE = Plane(
    "workers",
    "Workers",
    icon="cpu",
    description="The workers the backends hold, redrawn every second.",
    meta={"editable": True, "full_width": False},
    cells=(("counts", COUNTS), ("workers", TABLE)),
    group="System",
    backend="async",
)
