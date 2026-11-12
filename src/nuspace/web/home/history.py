"""Home's ``history`` cell: recent pages, as tiles of icon and title.

One list of plane ids in the Web store, small: ``Web.recents``, newest
first, kept to 50 by the store. A trail, so the newest :data:`TILES` still
in the space draw and nothing more.

A tile is a page link: the plane's icon and title, never its parents.
Removed planes are skipped. Cost: O(50), two reads each.

Reconciliation, two flows side by side:

- the list: drawn again when it changes or a plane is removed (one append
  to ``Space.indexes.removed``): each tile written in place, keyed by its
  plane, the tiles of planes no longer listed dropped, the rest put in
  list order;
- the tiles: one arm per plane shown (:class:`nu.ReconcileLatestEach`),
  each redrawing its own tile when its plane's name or icon changes. A
  rename elsewhere in the space wakes nothing here.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from ..ops import page
from ..shapes import Web


__all__ = ["TILES", "View", "draw", "first", "out", "read", "shown", "tiles"]


#: Most tiles the group draws.
TILES = 8


def _live(held: nu.Nu, cap: int | None = None) -> nu.List:
    """The ids of a Web list still in the space, in list order, the first ``cap`` of them."""
    listed = nu.List(nu.If(held.exists(), nu.list(held), []))
    kept = listed.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p))).to_list()
    return nu.List(kept) if cap is None else nu.List(nu.List(kept)[0:cap])


def read() -> nu.Dict:
    """``{recent}``: the recents to draw, each page ``{id, title, icon, href}``. Bare read, bracket it."""
    recent = _live(Web.recents, TILES)
    return nu.Dict.of(recent=recent.iter().map(lambda p: page(nu.Str(p))).to_list())


# --- The view ------------------------------------------------------------------------------


class Section(nustd.ui.PageSection):
    """The ``history`` cell's node: recent pages as tiles, or an empty state when there are none."""

    tiles = nustd.ui.GridRef.slot(nustd.ui.PageLinkRef, max_columns=4, min_cell_width=160, gap=1)
    empty = nustd.ui.EmptyStateRef.slot(icon="history", size="sm")


class View(nu.Shape):
    """The ``history`` cell's root: a hairline over its section, as after any section on home."""

    rule = nustd.ui.DividerRef.slot()
    history = Section.slot(title="History", description="Recently opened", gap=3)


#: The tiles, keyed by plane id: a tile is one plane's, wherever it lands in the list.
TILES_REF = View.history.tiles


def _tile(plane: nu.StrArg, got: nu.Nu) -> nu.Nu:
    d = nu.Dict(got)
    return TILES_REF[plane].set(href=d["href"], title=d["title"], icon=d["icon"])


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`: the tiles in list order, or the empty line.

    Each tile is written in place, then the grid keeps only the listed
    planes and puts them in list order: a tile still listed is never redrawn
    from none.
    """
    recent = nu.List(nu.Dict(got)["recent"])
    shown = recent.iter().map(lambda p: nu.Str(nu.Dict(p)["id"])).to_list()
    written = nu.ForEachDo(recent, lambda p: _tile(nu.Str(nu.Dict(p)["id"]), p))
    tiles = written >> TILES_REF.keep(shown) >> TILES_REF.set_order(shown)
    empty = nu.IfDo(
        recent.len() == 0,
        View.history.empty.set(
            label="Nothing opened yet", description="Planes you open show here."
        ),
        View.history.empty.erase(),
    )
    return tiles >> empty


def draw() -> nu.Nu:
    """One read, then its drawing."""
    return nu.let(atomic(read()), show)


def first() -> nu.Nu:
    """The hairline over the section, drawn once."""
    return View.rule.init()


# --- Per tile ------------------------------------------------------------------------------


def shown() -> nu.List:
    """The planes whose tiles are drawn now: one arm each. Bare read."""
    return _live(Web.recents, TILES)


def tiles(at: nu.Attr) -> nu.Nu:
    """One tile's arm: redraw it when its plane's name or icon changes. Event: a miss is only stale."""
    plane = nu.Str(at)
    row = Space.planes[plane]
    changes = nu.OnAny(row.name.on_change(), row.icon.on_change())
    body = nu.let(atomic(page(plane)), lambda got: _tile(plane, got))
    return nu.ReactEvery(atomic(changes), body)


def _lists() -> nu.Nu:
    """What moves the list: a visit, or a plane removed anywhere."""
    return nu.OnAny(
        Web.recents.on_change(),
        Web.recents.on_children_change(),
        Space.indexes.removed.on_children_change(),
    )


def out() -> nu.Nu:
    """The cell's program: the list, and one arm per tile drawn."""
    return first() >> nu.ParallelAsync(
        nu.Reconcile(atomic(_lists()), draw()),
        nu.ReconcileLatestEach(atomic(shown()), atomic(_lists()), tiles),
    )
