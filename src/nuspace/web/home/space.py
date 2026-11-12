"""Home's ``space`` cell: the info line, the counts, and the planes and cells added per day.

Everything here is a cached value or a bounded read, never a scan:

- the info line off ``Space.info`` (3 reads), the versions read once when
  the cell is built, the uptime a stamp the browser ticks;
- planes, cells, specs and planes from specs off the home indexer's totals
  (:mod:`.indexer`, 4 reads);
- the calendar off the indexer's ``calendar``, one page of the days in the
  window, at most :data:`DAYS` rows.

It draws again only when ``Space.info`` or the indexer's totals change
(the indexer writes its totals in the same commit as the calendar, and
only when they moved). No timer.
"""

from __future__ import annotations

import datetime

import nu
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from . import common, indexer
from .common import Compact, SpaceName, SpaceWhere


__all__ = ["DAYS", "View", "draw", "out", "read", "show", "versions"]


#: The days the calendar reads: 53 weeks back from today, plus the week it starts in.
DAYS = 53 * 7 + 7


def versions() -> str:
    """``nuspace 0.6.3, nu 0.1.14``: the installed versions (:data:`.common.VERSIONS`), the missing left out."""
    return ", ".join(f"{label} {v}" for label, v in common.VERSIONS.items() if v)


def _since() -> str:
    """The day before the calendar's first day: a page of days starts past it."""
    return (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()


#: ``Since()``: the key a calendar page starts after.
Since = nu.host(_since, name="HomeCalendarSince")


def _days(rows: object) -> dict:
    """``[[day, planes, cells], ...]`` as the heatmap takes it: ``{day: {planes, cells}}``."""
    values: dict[str, dict[str, int]] = {}
    for day, planes, cells in rows or ():
        parts = {k: int(v or 0) for k, v in (("planes", planes), ("cells", cells)) if v}
        if parts:
            values[str(day)] = parts
    return values


#: ``CalendarValues(rows)``: the calendar rows as the heatmap's values.
CalendarValues = nu.host(_days, name="HomeCalendarValues")


# --- The read ------------------------------------------------------------------------------


def read() -> nu.Dict:
    """What the cell shows, one bare read: ``{path, opened_at, counting, planes, cells, specs, from_specs, days}``.

    ``days`` is ``[[day, planes, cells], ...]`` for the days in the window
    that had adds, one page of the indexer's calendar. Cost: about 12 reads
    plus one seek and at most :data:`DAYS` rows.
    """
    info = Space.info
    state = indexer.index()
    totals = state.totals
    calendar = state.calendar

    def day(at: nu.Attr) -> nu.List:
        d = nu.Str(at)
        return nu.List.of(d, calendar[d].planes.fallback(0), calendar[d].cells.fallback(0))

    window = calendar.keys(after=Since(), limit=DAYS)
    days = nu.If(calendar.exists(), nu.List(window).iter().map(day).to_list(), [])
    return nu.Dict.of(
        path=info.path.fallback(""),
        opened_at=info.opened_at.fallback(0.0),
        counting=state.cursor.cell.fallback("") == "",
        planes=totals.planes.fallback(0),
        cells=totals.cells.fallback(0),
        specs=totals.specs.fallback(0),
        from_specs=totals.from_specs.fallback(0),
        days=days,
    )


#: The calendar's title. Its header totals are the window's, not the space's: it says so.
CALENDAR_TITLE = "Added per day, past year"


# --- The view ------------------------------------------------------------------------------


class Info(nustd.ui.Line):
    """The line under the title: name, versions, uptime.

    One sentence: each run but the last ends in its own `` ·``, so on a
    narrow pane it wraps between runs and a line never starts with a dot.
    """

    name = nustd.ui.TextRef.slot(size="sm", weight="medium", tone="secondary")
    versions = nustd.ui.TextRef.slot(size="sm", tone="muted")
    up = nustd.ui.TextRef.slot(value="up", size="sm", tone="muted")
    uptime = nustd.ui.RelativeTimeRef.slot(mode="duration")


class Section(nustd.ui.PageSection):
    """The ``space`` cell's node: the path as its description, the info line, then a board.

    The board puts the counts beside the calendar where the pane is wide,
    one under the other where it is not.
    """

    info = Info.slot()
    board = nustd.ui.GridRef.slot(cols="minmax(0, 1fr) auto", gap=4, align="start", stack_below=760)


class View(nu.Shape):
    """The ``space`` cell's root."""

    space = Section.slot(title="Space", gap=4)


#: The board: the counts first, then the calendar.
BOARD = View.space.board

#: Plain counts, nothing temporal: one card, a stat each, wrapping by width.
COUNTS = BOARD[0, 0].to(nustd.ui.CardRef.slot(size="sm"))
STATS = COUNTS["stats"].to(nustd.ui.GridRef.slot(max_columns=3, min_cell_width=96, gap=4))

PLANES = STATS["planes"].to(nustd.ui.StatRef.slot(label="Planes"))
CELLS = STATS["cells"].to(nustd.ui.StatRef.slot(label="Cells"))
SPECS = STATS["specs"].to(nustd.ui.StatRef.slot(label="Specs"))

#: How many planes came from a spec, plain in the card's footer (a stat's delta is a trend).
FROM_SPECS = COUNTS.footer[0].to(nustd.ui.TextRef.slot(size="sm", tone="muted"))

#: The planes and cells added per day: a card the calendar scrolls inside when it runs out of room.
CALENDAR = (
    BOARD[0, 1]
    .to(nustd.ui.CardRef.slot(size="sm"))["calendar"]
    .to(
        nustd.ui.CalendarHeatmapRef.slot(title=CALENDAR_TITLE, suffix="added", peak_label="Busiest")
    )
)


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`. Writes only what the read says, no clock."""
    d = nu.Dict(got)
    counting = nu.Bool(d["counting"])

    def value(key: str) -> nu.Str:
        return nu.Str(nu.If(counting, "…", nu.Str(Compact(d[key]))))

    from_specs = nu.Int(d["from_specs"])
    delta = nu.If(
        counting,
        "counting",
        nu.Str(Compact(from_specs)) + nu.If(from_specs == 1, " plane", " planes") + " from specs",
    )
    opened = nu.Float(d["opened_at"])
    up = opened > 0
    info = View.space.info
    # Every run but the last ends in a dot. The versions are a constant of this
    # process: empty, they are left out at build.
    name = nu.Str(SpaceName(d["path"]))
    if VERSIONS:
        runs = info.name.set(name + " ·") >> info.versions.set(
            nu.Str(VERSIONS) + nu.If(up, " ·", "")
        )
    else:
        runs = info.name.set(name + nu.If(up, " ·", ""))
    return (
        View.space.set_description(nu.Str(SpaceWhere(d["path"])))
        >> runs
        >> nu.IfDo(up, info.up.set("up") >> info.uptime.set(opened * 1000, mode="duration"))
        >> PLANES.set(value("planes"), label="Planes")
        >> CELLS.set(value("cells"), label="Cells")
        >> SPECS.set(value("specs"), label="Specs")
        >> FROM_SPECS.set(nu.Str(delta))
        >> CALENDAR.set(CalendarValues(d["days"]), title=CALENDAR_TITLE)
    )


#: Read once, as the module is imported: a running term does not ask importlib.
VERSIONS = versions()


def draw() -> nu.Nu:
    """One read, then its drawing."""
    return nu.let(atomic(read()), show)


def out() -> nu.Nu:
    """The cell's program: draw, then again whenever the info or the indexer's totals move."""
    totals = indexer.index().totals
    changes = nu.OnAny(Space.info.on_children_change(), totals.on_children_change())
    return nu.Reconcile(atomic(changes), draw())
