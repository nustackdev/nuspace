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
import importlib.metadata
from pathlib import Path

import nu
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from . import indexer
from .common import Compact


__all__ = ["DAYS", "View", "draw", "out", "read", "show", "versions"]


#: The days the calendar reads: 53 weeks back from today, plus the week it starts in.
DAYS = 53 * 7 + 7


def versions() -> str:
    """``nuspace 0.6.3, nu 0.1.14``: the installed versions, read in this process."""

    def version(name: str) -> str:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return ""

    # nu ships as the ``nucore`` distribution.
    found = ((label, version(dist)) for label, dist in (("nuspace", "nuspace"), ("nu", "nucore")))
    return ", ".join(f"{label} {v}" for label, v in found if v)


def _since() -> str:
    """The day before the calendar's first day: a page of days starts past it."""
    return (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()


#: ``Since()``: the key a calendar page starts after.
Since = nu.host(_since, name="HomeCalendarSince")


def _name(path: object) -> str:
    text = str(path or "").rstrip("/")
    return Path(text).name if text else "Throwaway store"


def _where(path: object) -> str:
    text = str(path or "")
    home = str(Path.home())
    return "~" + text[len(home) :] if text == home or text.startswith(home + "/") else text


def _days(rows: object) -> dict:
    """``[[day, planes, cells], ...]`` as the heatmap takes it: ``{day: {planes, cells}}``."""
    values: dict[str, dict[str, int]] = {}
    for day, planes, cells in rows or ():
        parts = {k: int(v or 0) for k, v in (("planes", planes), ("cells", cells)) if v}
        if parts:
            values[str(day)] = parts
    return values


#: ``SpaceName(path)``: the space's name, its directory's base name.
SpaceName = nu.host(_name, name="HomeSpaceName")

#: ``SpaceWhere(path)``: the path with the home directory as ``~``.
SpaceWhere = nu.host(_where, name="HomeSpaceWhere")

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


class Info(nustd.ui.Row):
    """The first line: name, path, versions, uptime."""

    name = nustd.ui.TextRef.slot(size="sm", weight="medium", tone="secondary")
    dot1 = nustd.ui.TextRef.slot(value="·", size="sm", tone="muted")
    path = nustd.ui.TextRef.slot(size="sm", tone="muted", mono=True)
    dot2 = nustd.ui.TextRef.slot(value="·", size="sm", tone="muted")
    versions = nustd.ui.TextRef.slot(size="sm", tone="muted")
    dot3 = nustd.ui.TextRef.slot(value="·", size="sm", tone="muted")
    up = nustd.ui.TextRef.slot(value="up", size="sm", tone="muted")
    uptime = nustd.ui.RelativeTimeRef.slot(mode="duration")


class Specs(nustd.ui.Column):
    """The specs count, and how many planes came from one under it, plain (a stat's delta is a trend)."""

    stat = nustd.ui.StatRef.slot(label="Specs")
    from_specs = nustd.ui.TextRef.slot(size="sm", tone="muted")


class Counts(nustd.ui.Grid):
    """Plain counts, nothing temporal."""

    planes = nustd.ui.StatRef.slot(label="Planes")
    cells = nustd.ui.StatRef.slot(label="Cells")
    specs = Specs.slot(gap=1)


class Stats(nustd.ui.Box):
    """The counts in a frame."""

    counts = Counts.slot(columns=3, min_width=120, gap=4)


class Body(nustd.ui.Row):
    """Counts on the left, the calendar beside them; the calendar wraps under on a narrow pane."""

    stats = Stats.slot()
    calendar = nustd.ui.CalendarHeatmapRef.slot(
        title=CALENDAR_TITLE, suffix="added", peak_label="Busiest"
    )


class Block(nustd.ui.Column):
    """The ``space`` cell's node."""

    title = nustd.ui.HeadingRef.slot(label="Space", level=2)
    info = Info.slot(gap=2, wrap=True, align="baseline")
    body = Body.slot(gap=7, wrap=True, align="start", min_width=280)


class View(nu.Shape):
    """The ``space`` cell's root."""

    space = Block.slot(gap=3)


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`. Writes only what the read says, no clock."""
    d = nu.Dict(got)
    view = View.space
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
    info = view.info
    # The versions are a constant of this process: an empty one is left out at build.
    shown = (info.dot2.set("·") >> info.versions.set(VERSIONS)) if VERSIONS else nu.Noop()
    return (
        view.title.set("Space", level=2)
        >> info.name.set(SpaceName(d["path"]))
        >> info.dot1.set("·")
        >> info.path.set(SpaceWhere(d["path"]))
        >> shown
        >> nu.IfDo(
            opened > 0,
            info.dot3.set("·")
            >> info.up.set("up")
            >> info.uptime.set(opened * 1000, mode="duration"),
        )
        >> view.body.stats.counts.planes.set(value("planes"), label="Planes")
        >> view.body.stats.counts.cells.set(value("cells"), label="Cells")
        >> view.body.stats.counts.specs.stat.set(value("specs"), label="Specs")
        >> view.body.stats.counts.specs.from_specs.set(nu.Str(delta))
        >> view.body.calendar.set(CalendarValues(d["days"]), title=CALENDAR_TITLE)
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
