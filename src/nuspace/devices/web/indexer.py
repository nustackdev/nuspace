"""The home indexer: counts the planes and cells added to the space, by day, for Home to read.

A plane with the fixed id :data:`PLANE`, made at open where missing
(:mod:`.planes`). It is system (remove refuses it), runs on ``async``, and
is not on the web, so the sidebar never lists it. Two reactions wake it:
one on planes added, one on cells added. Runs never do.

The web driver also asks for one run at every open (:func:`wake`), so
Home never waits for an add. Each run is one catch up pass, then it ends:
nothing stays resident. The
pass walks ``Space.planes`` and ``Space.cells`` in key order past its
cursors. Minted ids are time ordered (``p_<12 hex ms>_...``, ``c_...``,
see :func:`~nuspace.utils.interactions.mint_ordered_id`), so key order is
creation order and the two dicts read as creation logs. Fixed ids (root,
the system and web planes and their cells) carry no prefix and are
skipped.

Counts are created only: a removed row still counts, a restore adds
nothing. Cells of a system plane are not counted (the reactions plane's
cells are reactions, the indexer's own two among them). Misses are
accepted, this feeds a status page: a row added mid run waits for the next
add, and an id minted long before its row landed sorts behind the cursor.

State, at ``State.planes["home_indexer"]`` (:class:`Index`, via
:func:`index`); only indexer runs write it, except :func:`ensure` keeping
the reaction ids:

- ``calendar[day]``: ``{planes, cells}`` added that day, ``day`` the
  ``YYYY-MM-DD`` local date of ``created_at``;
- ``cursor``: ``{plane, cell}``, the last ids read, ``""`` before the first
  pass (Home shows "counting" while ``cursor.cell == ""``);
- ``totals``: ``{planes, cells}`` summed over the calendar on every page, so
  they never drift from it; ``from_specs`` the planes made from a spec;
  ``specs`` the plane specs installed;
- ``reactions``: ``{planes, cells}``, the two reaction ids, kept so ensure
  adds each one once.

Each page is one ``nuspace.atomic``: Space read from a snapshot, one State
commit holding the calendar, the cursors and the totals. A crash before the
commit reads the page again; after it, the page is done. Nothing is
counted twice.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.places import at
from nuspace.shapes import Space
from nuspace.system import reactions
from nustd.datetime import date


__all__ = [
    "BACKEND",
    "CELL",
    "CELLS",
    "ICON",
    "NAME",
    "PAGE",
    "PLANE",
    "PROG",
    "Cursor",
    "Day",
    "Index",
    "Reactions",
    "Totals",
    "catch_up",
    "ensure_reactions",
    "index",
    "out",
    "specs_installed",
    "step",
    "wake",
]


#: The plane id, fixed and reserved.
PLANE = "home_indexer"

#: What the plane is called.
NAME = "Home indexer"

#: Its icon.
ICON = ""

#: What its runs execute on: its pass awaits the stores, it never blocks.
BACKEND = "async"

#: Its one cell's name, and its fixed id (``<plane>_<name>``, as the web planes' cells).
CELL = "main"

#: The cell's prog: a shim, the code is here.
PROG = """\
from nuspace.devices.web.indexer import out
"""

#: The plane's cells, as ``(name, source)``.
CELLS = ((CELL, PROG),)

#: The most keys one page reads from each dict.
PAGE = 1000

#: The prefix of a minted plane id and of a minted cell id.
PLANE_PREFIX = "p_"
CELL_PREFIX = "c_"

#: The reactions' changes, as source (``Space`` is in a reaction's scope).
PLANES_ADDED = "Space.planes.on_children_change()"
CELLS_ADDED = "Space.cells.on_children_change()"


class Day(nu.Shape):
    """One day of the calendar: the planes and cells added that day."""

    planes = nustd.kv.IntRef.slot()
    cells = nustd.kv.IntRef.slot()


class Cursor(nu.Shape):
    """The last plane id and cell id a pass read, ``""`` (or absent) before the first."""

    plane = nustd.kv.StrRef.slot()
    cell = nustd.kv.StrRef.slot()


class Totals(nu.Shape):
    """The counts Home shows.

    ``planes`` and ``cells`` are sums over the calendar, written with it.
    ``from_specs`` counts planes made from a spec. ``specs`` is how many
    plane specs are installed, as the indexer's process sees the registry.
    """

    planes = nustd.kv.IntRef.slot()
    cells = nustd.kv.IntRef.slot()
    from_specs = nustd.kv.IntRef.slot()
    specs = nustd.kv.IntRef.slot()


class Reactions(nu.Shape):
    """The ids of the two reactions that wake the indexer."""

    planes = nustd.kv.StrRef.slot()
    cells = nustd.kv.StrRef.slot()


class Index(nu.Shape):
    """The indexer's state, at ``State.planes["home_indexer"]``. See the module."""

    calendar = nustd.kv.DictRef.slot(Day)
    cursor = nustd.kv.ShapeRef.slot(Cursor)
    totals = nustd.kv.ShapeRef.slot(Totals)
    reactions = nustd.kv.ShapeRef.slot(Reactions)


def index() -> Index:
    """The indexer's state: ``State.planes["home_indexer"]`` read through :class:`Index`."""
    return at.plane(id=PLANE).state(Index)


def specs_installed() -> int:
    """How many plane specs the installed packages register, read in this process."""
    from nuspace.specs.registry import _installed

    return len(_installed().registry.planes)


# --- The pass ---------------------------------------------------------------------------


def _after(rows: nu.Nu, cursor: nu.Str, prefix: str, limit: int) -> nu.List:
    """Up to ``limit`` minted ids of ``rows`` past ``cursor``, in key order.

    Minted ids share a prefix and sort together, so the page starts at the
    prefix when there is no cursor yet, and anything past the minted range
    (a fixed id) is dropped.
    """
    start = nu.Str(nu.If(cursor == "", prefix, cursor))
    page = rows.keys(after=start, limit=limit)
    return page.iter().filter(lambda k: nu.Str(k).startswith(prefix)).to_list()


def _day(stamp: nu.Nu) -> nu.Str:
    """The local date of a ``created_at`` stamp, ``YYYY-MM-DD``."""
    return date.from_timestamp(stamp).isoformat()


def _days(rows: nu.Nu, ids: nu.List, counted) -> nu.List:  # noqa: ANN001
    """The created day of each id ``counted`` keeps, one entry per id."""
    kept = ids.iter().filter(lambda i: counted(nu.Str(i)))
    return kept.map(lambda i: _day(rows[nu.Str(i)].created_at)).to_list()


def _plane_counted(p: nu.Str) -> nu.Bool:
    return Space.planes[p].created_at.exists()


def _cell_counted(c: nu.Str) -> nu.Bool:
    row = Space.cells[c]
    on_system = Space.planes[row.plane.fallback("")].system.fallback(False)
    return row.created_at.exists().and_(on_system.not_())


def _from_spec(p: nu.Str) -> nu.Bool:
    return Space.planes[p].spec.fallback("") != ""


def _add(days: nu.List, field: str) -> nu.Nu:
    """Each distinct day of ``days`` gets its count of entries added to ``calendar[day].<field>``."""
    calendar = index().calendar

    def one(at_: nu.Attr) -> nu.Nu:
        slot = getattr(calendar[nu.Str(at_)], field)
        return slot.set(slot.fallback(0) + days.count(nu.Str(at_)))

    return nu.ForEachDo(days.iter().unique(), one)


def _summed(field: str) -> nu.Int:
    """``field`` summed over every day of the calendar. O(days)."""
    calendar = index().calendar
    days = nu.List(nu.If(calendar.exists(), nu.list(calendar.keys()), []))
    return nu.Int(days.iter().map(lambda d: getattr(calendar[nu.Str(d)], field).fallback(0)).sum())


def _set_if_changed(slot: nu.Nu, value: nu.Nu) -> nu.Nu:
    return nu.let(value, lambda v: nu.IfDo(slot.fallback(-1) != v, slot.set(v)))


def step(*, specs: int = 0, limit: int = PAGE) -> nu.Nu:
    """One page of the pass: a bare term, the caller brackets it in one ``atomic``.

    Reads up to ``limit`` plane ids and ``limit`` cell ids past the cursors,
    adds each one to its created day, moves the cursors to the last ids
    read, then writes the totals summed over the calendar where they moved.

    Args:
        specs: What ``totals.specs`` is set to.
        limit: The most keys read from each dict.
    """
    state = index()
    cursor = state.cursor
    totals = state.totals

    def counted(ps: nu.Attr, cs: nu.Attr) -> nu.Nu:
        planes, cells = nu.List(ps), nu.List(cs)
        from_specs = planes.iter().filter(lambda p: _from_spec(nu.Str(p))).count()
        add = (
            nu.let(
                _days(Space.planes, planes, _plane_counted), lambda d: _add(nu.List(d), "planes")
            )
            >> nu.let(_days(Space.cells, cells, _cell_counted), lambda d: _add(nu.List(d), "cells"))
            >> nu.IfDo(
                from_specs > 0, totals.from_specs.set(totals.from_specs.fallback(0) + from_specs)
            )
        )
        moved = nu.IfDo(
            planes.len() > 0, cursor.plane.set(nu.Str(planes.iter().last()))
        ) >> nu.IfDo(cells.len() > 0, cursor.cell.set(nu.Str(cells.iter().last())))
        sums = (
            _set_if_changed(totals.planes, _summed("planes"))
            >> _set_if_changed(totals.cells, _summed("cells"))
            >> _set_if_changed(totals.specs, nu.Int(specs))
        )
        return add >> moved >> sums

    plane_page = _after(Space.planes, cursor.plane.fallback(""), PLANE_PREFIX, limit)
    cell_page = _after(Space.cells, cursor.cell.fallback(""), CELL_PREFIX, limit)
    return nu.let(plane_page, lambda ps: nu.let(cell_page, lambda cs: counted(ps, cs)))


def _pending() -> nu.Bool:
    """Whether any minted plane or cell id lies past the cursors: two one key reads."""
    cursor = index().cursor
    planes = _after(Space.planes, cursor.plane.fallback(""), PLANE_PREFIX, 1)
    cells = _after(Space.cells, cursor.cell.fallback(""), CELL_PREFIX, 1)
    return (planes.len() > 0).or_(cells.len() > 0)


def catch_up(*, specs: int = 0, limit: int = PAGE) -> nu.Nu:
    """The whole pass: one atomic :func:`step` per page while anything lies past the cursors.

    The first run is the same pass from empty cursors. A crash between
    pages resumes at the cursor. The last page always writes ``totals``, so
    a space with nothing minted still reads ``0`` once a pass ran.

    Args:
        specs: What ``totals.specs`` is set to.
        limit: The most keys a page reads from each dict.
    """
    page = atomic(step(specs=specs, limit=limit))
    return page >> nu.WhileDo(atomic(_pending()), page)


def out() -> nu.Nu:
    """The indexer cell's program: one catch up pass, then the run ends."""
    return catch_up(specs=specs_installed())


# --- Made at open -------------------------------------------------------------------------


def _kept(slot: nu.Nu, change: str) -> nu.Nu:
    """A reaction on ``change`` running the indexer, added only when ``slot`` keeps no id yet."""
    added = reactions.add(change, PLANE, into=slot)
    return nu.IfDo(atomic(slot.fallback("") == ""), added)


def ensure_reactions() -> nu.Nu:
    """The two reactions that wake the indexer, each added once, its id kept in ``Index.reactions``.

    Only once the reactions plane is there (``nuspace.system.ensure``), as it
    is in every open; a store without it gets none. Wrappers, bare: a few
    commits per reaction added, one read when both are kept.
    """
    kept = index().reactions
    adds = _kept(kept.planes, PLANES_ADDED) >> _kept(kept.cells, CELLS_ADDED)
    there = atomic(ops.plane.exists(reactions.PLANE).and_(ops.plane.exists(PLANE)))
    return nu.IfDo(there, adds)


def wake() -> nu.Nu:
    """One indexer run asked for at open, the way its planes reaction asks: ``reactions.up_plane``.

    Recorded ``by`` that reaction, and skipped while the run it asked for
    last is live, as a reaction's own wake is. The pass goes on from the
    cursor, so it is cheap, and it catches what landed mid run or while the
    space was closed. Nothing before :func:`ensure_reactions` kept the id.
    Run it only where a kernel will run the record (the web driver at open).
    """
    kept = atomic(index().reactions.planes.fallback(""))

    def asked(reaction: nu.Attr) -> nu.Nu:
        r = nu.Str(reaction)
        return nu.IfDo(r != "", reactions.up_plane(PLANE, r))

    return nu.let(kept, asked)
