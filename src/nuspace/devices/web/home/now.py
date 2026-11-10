"""Home's ``now`` cell: the plane runs live right now, a row each.

Read off ``Space.exec.indexes.live`` alone, never history:

- **Rows.** ``live.plane_runs`` in key order (oldest run first, so a row
  stays where it is). Runs of system planes (``Space.planes[p].system``)
  are left out unless the viewer turns the switch on. The first
  :data:`ROWS` draw; the rest are counted for an honest ``+N more
  running``, in either mode. The walk is O(live runs).
- **Per row:** the plane's icon and title; its cells as status squares,
  :data:`SQUARES` at most, then the full count; how many failed; the
  backend and the workers the run holds; how long it is up (a stamp the
  browser ticks); who asked.
- **Squares.** Counts per state from the live sets, not one read per cell:
  failed is the run's failed set, starting the live cell runs not started
  yet (the first :data:`SAMPLE` looked at), running the other live ones,
  idle the plane's cells with no live run. The total is the plane's cells,
  a walk of that one plane's list.

- **The switch.** "System runs", off by default. Its state is the
  viewer's, kept in the browser like any switch (one per pane run), never
  in the space: two tabs can each have it their own way.

It draws again when a run goes live or ends, a cell run starts, ends or
fails, or the switch flips, at most once a :data:`GAP`: a draw, then a
rest, changes during the rest merged into one more draw. With nothing
changing, nothing draws.

The section's top heading, Execution, is drawn here: Now and Recent
(:mod:`.runs`) sit under it.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from ..nav import BY as NAV
from .common import LIVE, Compact, ids, page, title


__all__ = [
    "GAP",
    "LABELS",
    "ROWS",
    "SAMPLE",
    "SQUARES",
    "SWITCH",
    "View",
    "by",
    "draw",
    "first",
    "out",
    "read",
    "squares",
    "system",
    "user_run",
]


#: Most rows drawn; the rest is one "+N more running" line.
ROWS = 10

#: Most status squares a row draws; past them, an ellipsis and the count.
SQUARES = 10

#: How many of a run's live cell runs are looked at for "starting".
SAMPLE = 100

#: The least time between two draws, in seconds.
GAP = 1.0

#: A tone's words, for the hover title and screen readers.
LABELS = {
    "danger": "failed",
    "info": "starting",
    "ok": "running",
    "warn": "invalid",
    "neutral": "stopped",
    "empty": "idle",
}


def by(asked: object, system: object) -> str:
    """Who asked for a run, in words: a system plane, a tab, you, or the name it was given.

    ``system`` is the title of the plane the asking cell is on when that
    plane is system (a reaction asks from the reactions plane), else ``""``.
    """
    who = str(asked or "")
    if system:
        return str(system)
    if who == NAV:
        return "tab"
    return who or "you"


def squares(total: object, failed: object, live: object, starting: object) -> dict:
    """A run's cells as status square counts: every cell once, the sum is ``total``."""
    total, failed, live, starting = (int(x or 0) for x in (total, failed, live, starting))
    starting = min(starting, live)
    failed = min(failed, total)
    live = min(live, total - failed)
    starting = min(starting, live)
    return {
        "danger": failed,
        "info": starting,
        "ok": live - starting,
        "empty": max(total - failed - live, 0),
    }


#: ``By(asked, system)``: :func:`by` as a term.
By = nu.host(by, name="HomeBy")

#: ``Squares(total, failed, live, starting)``: :func:`squares` as a term.
Squares = nu.host(squares, name="HomeSquares")


# --- The read ------------------------------------------------------------------------------


def _row(at: nu.Attr) -> nu.Dict:
    r = nu.Str(at)
    run = Space.exec.plane_runs[r]
    plane = nu.Str(run.plane.fallback(""))
    asked = nu.Str(run.by.fallback(""))
    live = ids(LIVE.plane_run_to_cell_runs[r].ids)
    sample = nu.List(live[0:SAMPLE])
    starting = sample.iter().filter(
        lambda c: Space.exec.cell_runs[nu.Str(c)].started_at.exists().not_()
    )
    cells = Space.planes[plane].cells
    total = nu.If(cells.exists(), nu.list(cells.keys()).len(), 0)
    failed = ids(LIVE.plane_run_to_failed_cells[r].ids).len()
    return nu.Dict.of(
        run=r,
        page=page(plane),
        backend=run.backend.fallback(""),
        workers=ids(LIVE.plane_run_to_workers[r].ids).len(),
        failed=failed,
        total=total,
        squares=Squares(total, failed, live.len(), starting.count()),
        started_at=run.started_at.fallback(run.created_at.fallback(0.0)),
        by=By(asked, _system_asker(asked)),
    )


def _system_asker(asked: nu.Str) -> nu.Str:
    """The title of the plane the asking cell is on, when that plane is system, else ``""``. Up to 3 reads."""
    on = nu.Str(nu.If(asked == "", "", Space.cells[asked].plane.fallback("")))
    system = Space.planes[on].system.fallback(False)
    return nu.Str(nu.If(on == "", "", nu.If(system, title(on), "")))


def user_run(run: nu.StrArg) -> nu.Bool:
    """Whether a plane run is of a plane that is not system: Home shows the space's own work. 2 reads."""
    plane = Space.exec.plane_runs[run].plane.fallback("")
    return Space.planes[plane].system.fallback(False).not_()


def read(system: nu.BoolArg = False) -> nu.Dict:
    """``{total, rows}``: how many plane runs are live, and the first :data:`ROWS`.

    Runs of system planes (their ``system`` flag set) count only when
    ``system`` is true; off, they are left out, as the counts leave them
    out. Cost: O(live runs) for the count, 2 reads each when filtering,
    then per row a few reads plus O(its plane's cells) and O(its live cell
    runs). Bare read, bracket it.
    """
    live = ids(LIVE.plane_runs)
    mine = live.iter().filter(lambda r: user_run(nu.Str(r))).to_list()
    runs = nu.List(nu.If(system, live, mine))
    shown = nu.List(runs[0:ROWS])
    return nu.Dict.of(total=runs.len(), rows=shown.iter().map(_row).to_list())


# --- The view ------------------------------------------------------------------------------


class Title(nustd.ui.Row):
    """Now and how many runs it counts."""

    title = nustd.ui.HeadingRef.slot(label="Now", level=3)
    count = nustd.ui.TextRef.slot(size="sm", tone="muted")


class Head(nustd.ui.Row):
    """The Now subsection's head: its title on the left, the system runs switch on the right."""

    title = Title.slot(gap=3, align="baseline")
    system = nustd.ui.SwitchRef.slot(label="System runs")


class Columns(nustd.ui.Grid):
    """The column names, on the same grid as a row."""

    plane = nustd.ui.TextRef.slot(value="Plane", size="xs", tone="muted")
    cells = nustd.ui.TextRef.slot(value="Cells", size="xs", tone="muted")
    count = nustd.ui.TextRef.slot(value="Count", size="xs", tone="muted")
    backend = nustd.ui.TextRef.slot(value="Backend", size="xs", tone="muted")
    up = nustd.ui.TextRef.slot(value="Up", size="xs", tone="muted")
    by = nustd.ui.TextRef.slot(value="By", size="xs", tone="muted")


class Count(nustd.ui.Row):
    """Failed, then the cells counted."""

    failed = nustd.ui.TextRef.slot(size="sm", tone="danger")
    total = nustd.ui.TextRef.slot(size="sm")


class Backend(nustd.ui.Row):
    """The backend and the workers held."""

    name = nustd.ui.TextRef.slot(size="sm", mono=True)
    workers = nustd.ui.TextRef.slot(size="sm", tone="muted")


#: Each row's columns as grid spans: the plane, the cells and the backend take three, the count two.
SPANS = {"plane": 3, "cells": 3, "count": 2, "backend": 3}

#: Columns on a row's grid: the six columns, four of them wider.
COLUMNS = 13

#: A row's grid, the column names' too, so the two line up.
GRID = {"columns": COLUMNS, "min_width": 24, "gap": 2, "spans": SPANS}


class RunRow(nustd.ui.Grid):
    """One live plane run. Its grid props are its own, so a templated row carries them."""

    plane = nustd.ui.PageLinkRef.slot(variant="inline")
    cells = nustd.ui.StatusSquaresRef.slot(max_items=SQUARES, labels=LABELS, total="never")
    count = Count.slot(gap=2, justify="end")
    backend = Backend.slot(gap=2, align="baseline")
    up = nustd.ui.RelativeTimeRef.slot(mode="duration")
    by = nustd.ui.TextRef.slot(size="sm", tone="secondary")

    @classmethod
    def slot(cls, item: object = None, /, **props: object) -> RunRow:  # type: ignore[override]
        """The row's slot, its grid props filled in: ``ref[key]`` builds a row from this."""
        return super().slot(item, **{**GRID, **props})  # type: ignore[arg-type]


class Block(nustd.ui.Column):
    """The ``now`` cell's node."""

    title = nustd.ui.HeadingRef.slot(label="Execution", level=2)
    head = Head.slot(gap=3, align="center", justify="between")
    columns = Columns.slot(**GRID)
    rows = nustd.ui.ColumnRef.slot(RunRow, gap=1)
    more = nustd.ui.TextRef.slot(size="sm", tone="muted")
    empty = nustd.ui.TextRef.slot(size="sm", tone="muted")


class View(nu.Shape):
    """The ``now`` cell's root."""

    now = Block.slot(gap=2)


def _drawn(i: int, got: nu.Nu) -> nu.Nu:
    d = nu.Dict(got)
    p = nu.Dict(d["page"])
    row = View.now.rows[f"r{i}"]
    failed = nu.Int(d["failed"])
    workers = nu.Int(d["workers"])
    return (
        row.plane.set(href=p["href"], title=p["title"], icon=p["icon"])
        >> row.cells.set(d["squares"])
        >> nu.IfDo(
            failed > 0,
            row.count.failed.set(nu.Str(Compact(failed)) + " failed"),
            row.count.failed.erase(),
        )
        >> row.count.total.set(nu.Str(Compact(d["total"])))
        >> row.backend.name.set(nu.Str(d["backend"]))
        >> row.backend.workers.set(
            nu.Str(Compact(workers)) + nu.If(workers == 1, " worker", " workers")
        )
        >> row.up.set(nu.Float(d["started_at"]) * 1000, mode="duration")
        >> row.by.set(nu.Str(d["by"]))
    )


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`: rows in order, the ones past the end erased."""
    d = nu.Dict(got)
    view = View.now
    rows = nu.List(d["rows"])
    total = nu.Int(d["total"])
    left = total - rows.len()
    drawn = nu.Sequential(
        *[
            nu.IfDo(rows.len() > i, _drawn(i, rows[i]), view.rows[f"r{i}"].erase())
            for i in range(ROWS)
        ]
    )
    head = view.head.title.title.set("Now", level=3) >> view.head.title.count.set(
        nu.If(
            total == 0,
            "",
            nu.Str(Compact(total)) + nu.If(total == 1, " plane run", " plane runs"),
        )
    )
    names = view.columns
    columns = nu.IfDo(
        total > 0,
        names.plane.set("Plane")
        >> names.cells.set("Cells")
        >> names.count.set("Count")
        >> names.backend.set("Backend")
        >> names.up.set("Up")
        >> names.by.set("By"),
        names.erase(),
    )
    return (
        view.title.set("Execution", level=2)
        >> head
        >> columns
        >> drawn
        >> nu.IfDo(
            left > 0,
            view.more.set(nu.Str("+") + nu.Str(Compact(left)) + " more running"),
            view.more.erase(),
        )
        >> nu.IfDo(total == 0, view.empty.set("Nothing running."), view.empty.erase())
    )


#: The switch: system runs shown or not. Its state lives in the browser, the viewer's own.
SWITCH = View.now.head.system


def system() -> nu.Bool:
    """Whether the viewer asked for system runs: the switch, off when not drawn yet. Reads the browser."""
    return nu.Bool(nu.bool(SWITCH).fallback(False))


def draw() -> nu.Nu:
    """The switch, one read, then its drawing."""
    return nu.let(system(), lambda on: nu.let(atomic(read(nu.Bool(on))), show))


def first() -> nu.Nu:
    """The heads, in order, the switch off: drawn once, so a redraw never flips the viewer's switch back."""
    view = View.now
    return (
        view.title.set("Execution", level=2)
        >> view.head.title.title.set("Now", level=3)
        >> SWITCH.set(False)
    )


def out() -> nu.Nu:
    """The cell's program: the heads, then a draw on every change to the live sets or the switch, a :data:`GAP` apart."""
    changes = nu.OnAny(
        LIVE.plane_runs.on_children_change(),
        LIVE.plane_run_to_cell_runs.on_descendants_change("*", "ids", "*"),
        LIVE.plane_run_to_failed_cells.on_descendants_change("*", "ids", "*"),
        LIVE.plane_run_to_workers.on_descendants_change("*", "ids", "*"),
    )
    flipped = SWITCH.on_change()
    return first() >> nu.Reconcile(nu.OnAny(atomic(changes), flipped), draw() >> nu.Delay(GAP))
