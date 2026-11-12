"""Home's ``now`` cell, Execution: Now, the plane runs live right now, a row each, then Recent.

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

- **The table.** One data table keyed by run, each column drawing its
  cells as a kind (a page link, status squares, a badge, a ticking
  duration): a draw replaces the rows whole, so a run that ended goes
  with no erase of its own.
- **The switch.** "System runs", off by default, on the section's head:
  one switch for Now and Recent (:mod:`.runs`). Its state is the
  viewer's, kept in the browser like any switch (one per pane run), never
  in the space: two tabs can each have it their own way.

It draws again when a run goes live or ends, a cell run starts, ends or
fails, or the switch flips, at most once a :data:`GAP`: a draw, then a
rest, changes during the rest merged into one more draw. With nothing
changing, nothing draws.

The whole Execution section is this cell: Now and Recent sit under its
title, each drawn again on its own changes, both on the switch.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from ..nav import BY as NAV
from . import runs
from .common import LIVE, Compact, Head, compact, ids, page, title


__all__ = [
    "COLUMNS",
    "GAP",
    "LABELS",
    "ROWS",
    "SAMPLE",
    "SQUARES",
    "SWITCH",
    "Now",
    "View",
    "by",
    "draw",
    "first",
    "out",
    "read",
    "recent",
    "rows",
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


# --- Shaping -------------------------------------------------------------------------------


def rows(got: object) -> list:
    """A read's rows as the table takes them: one mapping per run, keyed ``run``.

    Each value is what its column's cell draws (:data:`COLUMNS`): the plane a
    page link, the cells status square counts, a count of failed cells only
    when there are some (a blank cell draws nothing), the backend with the
    workers the run holds, the time up in ms.
    """
    out = []
    for raw in (dict(got or {})).get("rows") or ():
        row = dict(raw)
        failed = int(row.get("failed") or 0)
        workers = int(row.get("workers") or 0)
        held = f"{compact(workers)} {'worker' if workers == 1 else 'workers'}"
        out.append(
            {
                "run": str(row.get("run", "")),
                "plane": dict(row.get("page") or {}),
                "cells": {"counts": dict(row.get("squares") or {})},
                "failed": compact(failed) if failed else "",
                "backend": f"{row.get('backend') or ''}, {held}",
                "up": round(float(row.get("started_at") or 0.0) * 1000),
                "by": str(row.get("by") or ""),
            }
        )
    return out


#: ``Rows(read)``: :func:`rows` as a term.
Rows = nu.host(rows, name="HomeNowRows")


# --- The view ------------------------------------------------------------------------------


def _column(key: str, label: str, cell: object = None, **more: object) -> dict:
    column: dict = {"key": key, "label": label, "sortable": False, **more}
    if cell is not None:
        column["cell"] = cell
    return column


#: The table's columns, each cell drawn by its spec. Nothing sorts: the rows keep run order.
COLUMNS = [
    _column("plane", "Plane", nustd.ui.PageLinkRef.slot(variant="inline")),
    _column(
        "cells",
        "Cells",
        nustd.ui.StatusSquaresRef.slot(max_items=SQUARES, labels=LABELS, total="always"),
    ),
    _column("failed", "Failed", nustd.ui.BadgeRef.slot(variant="danger", size="sm"), align="right"),
    _column("backend", "Backend"),
    _column("up", "Up", nustd.ui.RelativeTimeRef.slot(mode="duration"), align="right"),
    _column("by", "By"),
]


class Now(nustd.ui.Column):
    """Now, under Execution: its head, then the table and an honest more, or an empty state."""

    head = Head.slot(gap=3, align="baseline")
    table = nustd.ui.DataTableRef.slot(
        columns=COLUMNS, row_key="run", label="Plane runs live now", striped=False
    )
    more = nustd.ui.TextRef.slot(size="sm", tone="muted")
    empty = nustd.ui.EmptyStateRef.slot(icon="activity", size="sm")


class Section(nustd.ui.PageSection):
    """The ``now`` cell's node, Execution: Now, then Recent (:mod:`.runs`), one switch for both."""

    actions = nustd.ui.SwitchRef.slot(label="System runs")
    now = Now.slot(gap=3)
    recent = runs.Recent.slot(gap=3)


class View(nu.Shape):
    """The ``now`` cell's root."""

    execution = Section.slot(
        title="Execution",
        description="Plane runs live now, and the last planes that ran",
        bordered=True,
        gap=8,
    )


#: The switch: system runs shown or not, in Now and Recent both. Its state lives in the
#: browser, the viewer's own.
SWITCH = View.execution.actions


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`: the rows replaced whole, keyed by run, and the counts."""
    d = nu.Dict(got)
    part = View.execution.now
    shown = nu.List(d["rows"])
    total = nu.Int(d["total"])
    left = total - shown.len()
    count = nu.If(
        total == 0, "", nu.Str(Compact(total)) + nu.If(total == 1, " plane run", " plane runs")
    )
    table = nu.IfDo(
        total > 0,
        part.table.set_rows(Rows(got)) >> part.table.display() >> part.empty.erase(),
        part.table.hide()
        >> part.empty.set(
            label="Nothing running", description="Plane runs show here while they run."
        ),
    )
    return (
        part.head.count.set(nu.Str(count))
        >> table
        >> nu.IfDo(
            left > 0,
            part.more.set(nu.Str("+") + nu.Str(Compact(left)) + " more running"),
            part.more.erase(),
        )
    )


def system() -> nu.Bool:
    """Whether the viewer asked for system runs: the switch, off when not drawn yet. Reads the browser."""
    return nu.Bool(nu.bool(SWITCH).fallback(False))


def draw() -> nu.Nu:
    """Now: the switch, one read, then its drawing."""
    return nu.let(system(), lambda on: nu.let(atomic(read(nu.Bool(on))), show))


def recent() -> nu.Nu:
    """Recent: the switch, then the walk and its drawing (:func:`.runs.draw`)."""
    return nu.let(system(), lambda on: runs.draw(View.execution.recent, nu.Bool(on)))


def first() -> nu.Nu:
    """The heads, the switch off: drawn once, so a redraw never flips the viewer's switch back."""
    section = View.execution
    return (
        section.now.head.title.set("Now", level=3)
        >> section.recent.head.title.set("Recent", level=3)
        >> SWITCH.set(False)
    )


def out() -> nu.Nu:
    """The cell's program: the heads, then Now and Recent, each drawn again on its own changes or the switch.

    Now at most once a :data:`GAP`, Recent once a :data:`.runs.GAP`.
    """
    live = nu.OnAny(
        LIVE.plane_runs.on_children_change(),
        LIVE.plane_run_to_cell_runs.on_descendants_change("*", "ids", "*"),
        LIVE.plane_run_to_failed_cells.on_descendants_change("*", "ids", "*"),
        LIVE.plane_run_to_workers.on_descendants_change("*", "ids", "*"),
    )
    return first() >> nu.ParallelAsync(
        nu.Reconcile(nu.OnAny(atomic(live), SWITCH.on_change()), draw() >> nu.Delay(GAP)),
        nu.Reconcile(
            nu.OnAny(atomic(runs.changes()), SWITCH.on_change()), recent() >> nu.Delay(runs.GAP)
        ),
    )
