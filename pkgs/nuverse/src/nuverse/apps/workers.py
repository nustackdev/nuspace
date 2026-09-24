"""The ``workers`` app: a live page of the kernel's workers.

Two cells, each redrawing once a second from one snapshot of the store: the
counts by status, and every worker, newest first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import App

from ._live import live_page


if TYPE_CHECKING:
    import nu


__all__ = ["APP", "COUNTS", "TABLE", "workers"]


COUNTS = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


def count(workers, status):
    w = nu.DictAttrRef("w")
    return nu.Count(nu.Filter(nu.Iter(workers), nu.Eq(w["status"], status), key="w"))


def draw():
    workers = nu.ListAttrRef("workers")
    tiles = [
        nustd.ui.StatRef(status).set(nu.ToStr(count(workers, status)), label=status.capitalize())
        for status in ("starting", "up", "stopping", "dead")
    ]
    return nustd.kv.Snapshot(
        nu.Let("workers", ops.workers(), nu.Sequential(*tiles)), scope=nuspace.Space
    )


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


def held(wid):
    flag = nuspace.Space.kernel.workers[wid].held
    return nu.If(flag.exists(), nu.If(nu.ToBool(flag), "yes", "no"), "no")


def age(t):
    now = nu.FloatAttrRef("now")
    return nu.If(nu.Is(t, None), nu.Str(""), nu.Format(now - t, ".0f") + nu.Str("s"))


def draw():
    w = nu.DictAttrRef("w")
    newest = nu.List(nu.Collect(nu.Reversed(ops.workers())))[0:30]
    row = nu.List.of(
        w["id"], w["kind"], w["status"], held(w["id"]),
        nu.Len(ops.live_runs(worker=w["id"])), age(w["started"]),
    )
    table = nustd.ui.TableRef("workers").set(
        nu.Dict.of(
            columns=["ID", "Kind", "Status", "Held", "Live runs", "Age"],
            rows=nu.Collect(nu.Map(nu.Iter(newest), row, key="w")),
        )
    )
    return nustd.kv.Snapshot(nu.Let("now", nustd.time.time(), table), scope=nuspace.Space)


def out():
    return draw() >> nu.ForeverDo(nu.DelayedDo(1.0, draw()))
"""


def workers(plane_id: nu.StrArg | None = None, name: nu.StrArg = "") -> nu.Nu:
    """A live workers page. Yields its id."""
    return live_page("workers", plane_id, name, [("counts", COUNTS), ("workers", TABLE)])


APP = App("workers", "Workers", workers, description="The kernel's workers, redrawn every second.")
