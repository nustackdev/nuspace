"""Home's ``history`` cell: recent pages, as tiles of icon and title.

One list of plane ids in the Web store, small: ``Web.recents``, newest
first, kept to 50 by the store. A trail, so the newest :data:`TILES` still
in the space draw and nothing more.

A tile is a page link: the plane's icon and title, never its parents.
Removed planes are skipped. Cost: O(50), two reads each.

Reconciliation, two flows side by side:

- the list: drawn again when it changes or a plane is removed (one append
  to ``Space.indexes.removed``), tiles written in order and the ones past
  the end erased, so the browser keeps them in order;
- the tiles: one arm per tile shown (:class:`nu.ReconcileLatestEach`), each
  redrawing its own tile when its plane's name or icon changes. A rename
  elsewhere in the space wakes nothing here.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from ..shapes import Web
from .common import page


__all__ = ["TILES", "View", "draw", "out", "read", "shown", "tiles"]


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


class GroupHead(nustd.ui.Row):
    """A group's icon and name."""

    icon = nustd.ui.IconRef.slot()
    label = nustd.ui.TextRef.slot(size="sm", weight="medium", tone="muted")


class Group(nustd.ui.Column):
    """A group of page tiles."""

    head = GroupHead.slot(gap=2)
    tiles = nustd.ui.GridRef.slot(nustd.ui.PageLinkRef, columns=4, min_width=160, gap=1)
    empty = nustd.ui.TextRef.slot(size="sm", tone="muted")


class Block(nustd.ui.Column):
    """The ``history`` cell's node."""

    title = nustd.ui.HeadingRef.slot(label="History", level=2)
    recent = Group.slot(gap=1)


class View(nu.Shape):
    """The ``history`` cell's root."""

    history = Block.slot(gap=3)


def tile(group: Group, i: nu.IntArg) -> nustd.ui.PageLinkRef:
    """Tile ``i`` of a group: a computed key, so tiles are as many as drawn."""
    return group.tiles[nu.Str("t") + nu.str(i)]


def _tile(group: Group, i: nu.IntArg, got: nu.Nu) -> nu.Nu:
    d = nu.Dict(got)
    return tile(group, i).set(href=d["href"], title=d["title"], icon=d["icon"])


def _group(group: Group, pages: nu.List, label: str, icon: str, none: str) -> nu.Nu:
    """One group: its head, its tiles in order, the rest erased, an empty line."""
    n = pages.len()
    tiles_ = nu.Sequential(
        *[nu.IfDo(n > i, _tile(group, i, pages[i]), tile(group, i).erase()) for i in range(TILES)]
    )
    empty = nu.IfDo(n == 0, group.empty.set(none), group.empty.erase())
    head = group.head.icon.set(icon) >> group.head.label.set(label)
    return head >> tiles_ >> empty


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`."""
    recent = nu.List(nu.Dict(got)["recent"])
    return View.history.title.set("History", level=2) >> _group(
        View.history.recent, recent, "Recent", "clock", "Nothing opened yet."
    )


def draw() -> nu.Nu:
    """One read, then its drawing."""
    return nu.let(atomic(read()), show)


# --- Per tile ------------------------------------------------------------------------------


def shown() -> nu.List:
    """The tiles drawn now, as ``"<index>|<plane>"``: one arm each. Bare read."""
    ids = _live(Web.recents, TILES)
    keyed = nu.List.of(
        *[nu.If(ids.len() > i, nu.Str(f"{i}|") + nu.Str(ids[i]), "") for i in range(TILES)]
    )
    return nu.List(keyed.iter().filter(lambda k: nu.Str(k) != "").to_list())


def tiles(at: nu.Attr) -> nu.Nu:
    """One tile's arm: redraw it when its plane's name or icon changes. Event: a miss is only stale."""
    parts = nu.List(nu.Str(at).split("|", 1))
    i, plane = nu.Str(parts[0]), nu.Str(parts[1])
    row = Space.planes[plane]
    changes = nu.OnAny(row.name.on_change(), row.icon.on_change())
    body = nu.let(atomic(page(plane)), lambda got: _tile(View.history.recent, i, got))
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
    return nu.ParallelAsync(
        nu.Reconcile(atomic(_lists()), draw()),
        nu.ReconcileLatestEach(atomic(shown()), atomic(_lists()), tiles),
    )
