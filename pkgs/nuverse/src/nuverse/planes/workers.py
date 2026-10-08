"""The ``workers`` Plane: the workers the backends hold, live.

Two cells, each drawn again when what is live changes, and only when what it
shows did: the counts per backend, and every live worker with the run it
serves. Read off ``workers_running``, so it costs what is up, never history.
Ages move with the clock, so the table is read again every minute too.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["COUNTS", "PLANE", "TABLE"]


COUNTS = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws


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
    return nu.let(ops.snapshot(ops.workers()), tiles)


out = redraws([nuspace.Space.kernel.workers_running.on_children_change()], ops.workers(), tiles)
"""


TABLE = """\
import nu
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws
from nuverse.planes.runs import age, lives


def cells_on(w):
    # The run's live cell runs placed on this worker: a walk of what is live.
    live = ops.cell_runs(nu.str(w["run"]), live=True).iter()
    return nu.Count(live.filter(lambda c: c["worker"] == w["id"]))


def rows():
    now = nustd.time.time()

    def row(w):
        name = nuspace.Space.planes[w["plane"]].name.fallback(w["plane"])
        return nu.List.of(
            w["id"], w["backend"], name, w["run"], cells_on(w), age(now, w["started_at"])
        )

    newest = nu.List(nu.Collect(nu.Reversed(ops.workers())))
    return newest.iter().map(row).to_list()


def table(shown):
    columns = ["ID", "Backend", "Plane", "Run", "Cells", "Age"]
    return nustd.ui.TableRef("workers").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(ops.snapshot(rows()), table)


out = redraws(lives(), rows(), table, every=60.0)
"""


PLANE = Plane(
    "workers",
    "Workers",
    icon="cpu",
    description="The workers the backends hold, kept live.",
    meta={"editable": True, "full_width": False},
    cells=(("counts", COUNTS), ("workers", TABLE)),
    group="System",
    backend="async",
)
