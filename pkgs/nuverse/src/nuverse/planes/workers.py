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
    w = nu.Attr("w")
    return nu.Count(nu.Filter(nu.Iter(workers), nu.Eq(w["backend"], backend), key="w"))


def tiles(workers):
    return nustd.ui.StatRef("up").set(nu.ToStr(nu.Len(workers)), label="Up") >> nu.Sequential(
        *[
            nustd.ui.StatRef(backend).set(nu.ToStr(count(workers, backend)), label=backend)
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


def plane_name(pid):
    name = nuspace.Space.planes[pid].name
    return nu.If(name.exists(), nu.ToStr(name), pid)


def age(now, t):
    return nu.If(nu.Is(t, None), nu.Str(""), nu.Format(nu.Float(now) - t, ".0f") + nu.Str("s"))


def cells_on(w):
    # The run's live cell runs placed on this worker: a walk of what is live.
    c = nu.Attr("c")
    live = nu.Iter(ops.cell_runs(nu.ToStr(w["run"]), live=True))
    return nu.Count(nu.Filter(live, nu.Eq(c["worker"], w["id"]), key="c"))


def table(now):
    w = nu.Attr("w")
    row = nu.List.of(
        w["id"], w["backend"], plane_name(w["plane"]), w["run"], cells_on(w), age(now, w["started_at"])
    )
    newest = nu.List(nu.Collect(nu.Reversed(ops.workers())))
    return nustd.ui.TableRef("workers").set(
        nu.Dict.of(
            columns=["ID", "Backend", "Plane", "Run", "Cells", "Age"],
            rows=nu.Collect(nu.Map(nu.Iter(newest), row, key="w")),
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
    backend="async",
)
