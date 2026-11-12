"""Home's Recent, under Execution: the last planes that ran, their runs on a timeline.

No run index of its own, read straight from ``Space.exec``, with caps:

- **Lanes.** ``Space.exec.plane_runs`` walked newest first, a page of
  :data:`PAGE` at a time, one read of each run's plane, until
  :data:`LANES` distinct planes are found. Which planes may become a lane
  is the walk's own predicate, set by the viewer's "System runs" switch:
  off (the default), planes with their ``system`` flag are skipped (their
  runs still count toward the budget); on, they are lanes like any other.
  Never a filter over lanes already found. The walk reads at most
  :data:`BUDGET` runs: one plane running thousands of times an hour could
  fill it, and then the lanes found so far show with a quiet note.
- **Per lane.** One page of the plane's history log, newest first,
  :data:`PER_LANE` runs at most, each an interval from start to end,
  colored by its exit. A run not ended reaches the window's end. A full
  page says so: its count reads ``100+ runs``.
- **Window.** From the oldest lane's newest run to now: variable, as long
  as it takes to show every lane.

Drawn by the ``now`` cell (:mod:`.now`), under Execution, beside Now:
one "System runs" switch, the section's, sets both. No live styling: Now
is the live view. It draws again when a run is added, a live one ends or
the switch flips, at most once a :data:`GAP`.

A home made before Recent moved has a ``runs`` cell of its own: its
:func:`out` draws nothing, so Recent shows once.
"""

from __future__ import annotations

import time

import nu
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from ..ops import page
from .common import HISTORY, LIVE, Compact, Head


__all__ = [
    "BUDGET",
    "GAP",
    "LANES",
    "LEGEND",
    "PAGE",
    "PER_LANE",
    "TONES",
    "Recent",
    "changes",
    "collect",
    "draw",
    "lanes",
    "out",
    "shape",
]


#: Most lanes: distinct planes that ran.
LANES = 20

#: Most runs a lane draws, its newest.
PER_LANE = 100

#: Most runs the walk for lanes reads.
BUDGET = 10_000

#: Runs one step of the walk reads.
PAGE = 500

#: The least time between two draws, in seconds.
GAP = 2.0

#: A run's exit as a timeline tone. Not ended yet draws as ok: Now shows what is live.
TONES = {"ok": "ok", "failed": "danger", "killed": "warn", "interrupted": "neutral", "": "ok"}

#: The tones named in the legend and the tooltips.
LEGEND = {"ok": "ok", "danger": "failed", "warn": "killed", "neutral": "interrupted"}


# --- The walk ------------------------------------------------------------------------------


class _Walk(nu.Shape):
    """The walk for lanes: the planes found, where the next page starts, runs read, more to read."""

    planes = nu.ListRef.slot(str)
    before = nu.StrRef.slot()
    read = nu.IntRef.slot()
    more = nu.BoolRef.slot()


def collect(
    into: nu.Nu,
    *,
    system: nu.BoolArg = False,
    lanes_: int = LANES,
    budget: int = BUDGET,
    size: int = PAGE,
) -> nu.Nu:
    """Write ``{lanes, read, cut}`` to ``into``: the newest ``lanes_`` distinct planes that ran, their runs.

    The walk: pages of ``size`` run ids newest first (one reverse seek
    each), one read of each run's plane. ``system`` is the walk's
    predicate: false, a system plane's runs are read and skipped (one more
    read each); true, a system plane is a lane like any other. It stops at
    ``lanes_`` planes, at
    the oldest run, or once ``budget`` runs are read: ``cut`` says the
    budget stopped it short. Then each plane's runs (:func:`lanes`).

    A loop yields nothing, so the result goes to ``into``, a mem slot the
    caller reads once this is done. Reads only: bracket it in one
    ``atomic``. Cost: at most ``budget`` reads plus a seek a page, then
    :data:`PER_LANE` x 3 reads a lane.
    """
    found, before, read_, more = _Walk.planes, _Walk.before, _Walk.read, _Walk.more
    runs = Space.exec.plane_runs

    def visit(at: nu.Attr) -> nu.Nu:
        plane = nu.Str(runs[nu.Str(at)].plane.fallback(""))
        new = (found.len() < lanes_).and_(plane != "").and_(found.contains(plane).not_())
        lane = nu.If(system, True, Space.planes[plane].system.fallback(False).not_())
        return nu.IfDo(new, nu.IfDo(lane, found.append(plane)))

    def step(held: nu.ObjectRef) -> nu.Nu:
        got = nu.List(held)
        return (
            nu.ForEachDo(got, visit)
            >> read_.set(read_ + got.len())
            >> more.set(got.len() == size)
            >> nu.IfDo(got.len() > 0, before.set(nu.Str(got.iter().last())))
        )

    next_page = nu.If(
        before == "",
        runs.reversed_keys(limit=size),
        runs.reversed_keys(before=before, limit=size),
    )
    going = more.and_(found.len() < lanes_).and_(read_ < budget)
    loop = nu.WhileDo(going, nu.let(nu.If(runs.exists(), next_page, []), step))
    result = nu.Dict.of(
        lanes=lanes(nu.list(found)),
        read=read_,
        cut=more.and_(found.len() < lanes_).and_(read_ >= budget),
    )
    # ``nu.List.of()``, not ``[]``: a literal list is one object for every run of
    # the built term, and ``append`` would grow it across draws (stale lanes).
    fresh = nu.List.of()
    return nu.Frame(_Walk, loop >> into.set(result), planes=fresh, before="", read=0, more=True)


def lanes(planes: nu.ListArg) -> nu.List:
    """Each plane's page and its newest :data:`PER_LANE` runs as ``[start, end, exit]``, seconds.

    One reverse seek on the plane's history log and 3 reads a run. A run
    not started yet starts at its creation; one not ended has ``end`` 0.
    """
    runs = Space.exec.plane_runs

    def run(at: nu.Attr) -> nu.List:
        row = runs[nu.Str(at)]
        start = row.started_at.fallback(row.created_at.fallback(0.0))
        return nu.List.of(start, row.ended_at.fallback(0.0), row.exit.fallback(""))

    def lane(at: nu.Attr) -> nu.Dict:
        plane = nu.Str(at)
        log = HISTORY.plane_to_plane_runs[plane].runs
        ids = nu.List(nu.If(log.exists(), log.reversed_keys(limit=PER_LANE), []))
        return nu.Dict.of(page=page(plane), runs=ids.iter().map(run).to_list())

    return nu.List(nu.List(planes).iter().map(lane).to_list())


# --- Shaping -------------------------------------------------------------------------------


def shape(got: object, now: object) -> dict:
    """A read as the timeline takes it: ``{lanes, start, end, note}``, times in ms.

    A lane whose page came back full reads ``"100+ runs"`` (``count_label``).

    The window runs from the oldest lane's newest run to ``now`` (seconds),
    a little before so that run shows, and never under a minute.
    """
    data = dict(got or {})
    end = float(now or time.time())
    out, newest = [], []
    for raw in data.get("lanes") or ():
        p = dict(raw.get("page") or {})
        items = []
        for start, ended, exit_ in raw.get("runs") or ():
            if not start:
                continue
            items.append(
                [
                    round(float(start) * 1000),
                    round(float(ended) * 1000) if ended else None,
                    TONES.get(str(exit_ or ""), "neutral"),
                ]
            )
        if not items:
            continue
        newest.append(items[0][0] / 1000)
        lane = {
            "id": str(p.get("id", "")),
            "title": str(p.get("title", "")),
            "icon": str(p.get("icon", "")),
            "href": str(p.get("href", "")),
            "items": items,
        }
        if len(items) >= PER_LANE:
            # One page read: the plane ran at least this often, maybe far more.
            lane["count_label"] = f"{PER_LANE}+ runs"
        out.append(lane)
    oldest = min(newest) if newest else end - 3600
    span = max(end - oldest, 60.0)
    start = end - span * 1.04
    notes = []
    if data.get("cut"):
        notes.append(
            f"Showing {len(out)}: the last {compact_budget()} runs are from {len(out)} planes."
        )
    return {
        "lanes": out,
        "start": round(start * 1000),
        "end": round(end * 1000),
        "note": " ".join(notes),
    }


def compact_budget() -> str:
    """The budget as a note writes it: ``10K``."""
    return f"{BUDGET // 1000}K" if BUDGET % 1000 == 0 else f"{BUDGET:,}"


def _now() -> float:
    return time.time()


#: ``Shaped(read, now)``: :func:`shape` as a term.
Shaped = nu.host(shape, name="HomeRunsShaped")

#: ``Clock()``: the host clock at draw time, the window's end.
Clock = nu.host(_now, name="HomeRunsClock")


# --- The view ------------------------------------------------------------------------------


class Recent(nustd.ui.Column):
    """Recent, under Execution (:mod:`.now` places it): its head, then the timeline or an empty state."""

    head = Head.slot(gap=3, align="baseline")
    timeline = nustd.ui.TimelineRef.slot(
        max_lanes=0, max_items=PER_LANE, noun="run", axis="clock", legend=LEGEND
    )
    empty = nustd.ui.EmptyStateRef.slot(icon="clock", size="sm")


def show(got: nu.ObjectRef, part: Recent) -> nu.Nu:
    """Draw one read into ``part``: the shaped lanes on the timeline, or an empty state when nothing ran."""

    def drawn(held: nu.ObjectRef) -> nu.Nu:
        s = nu.Dict(held)
        n = nu.List(s["lanes"]).len()
        timeline = (
            part.timeline.set(s["lanes"], start=s["start"], end=s["end"])
            >> part.timeline.set_note(nu.Str(s["note"]))
            >> part.empty.erase()
        )
        count = nu.Str(Compact(n)) + nu.If(n == 1, " plane", " planes")
        return nu.IfDo(
            n > 0,
            part.head.count.set(count) >> timeline,
            part.head.count.set("")
            >> part.timeline.erase()
            >> part.empty.set(
                label="Nothing has run yet", description="The last planes that ran show here."
            ),
        )

    return nu.let(Shaped(got, Clock()), drawn)


def draw(part: Recent, system: nu.BoolArg = False) -> nu.Nu:
    """One read into a mem slot, in one snapshot, then its drawing into ``part``.

    ``system`` is the walk's predicate (:func:`collect`): the viewer's switch,
    read by the caller.
    """
    return nu.let(None, lambda got: atomic(collect(got, system=system)) >> show(got, part))


def changes() -> nu.Nu:
    """What Recent draws again on: a run added, or a live one ending."""
    return nu.OnAny(
        Space.exec.plane_runs.on_children_change(),
        LIVE.plane_runs.on_children_change(),
    )


def out() -> nu.Nu:
    """An older home's ``runs`` cell: draws nothing, Recent is drawn under Execution by :mod:`.now`."""
    return nu.Noop()
