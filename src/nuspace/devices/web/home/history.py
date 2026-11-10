"""Home's ``history`` cell: pinned pages, then recent ones, as tiles of icon and title.

Two lists of plane ids in the Web store, both small:

- **Pinned** (``Web.pinned``, user order, uncapped): every pin still in the
  space is counted; at most :data:`TILES` tiles draw, and past that
  ``TILES - 1`` and one ``+N more pinned`` tile, so the count never lies.
- **Recent** (``Web.recents``, newest first, kept to 50 by the store): a
  trail, so the newest :data:`TILES` still in the space draw and nothing more.

A tile is a page link: the plane's icon and title, never its parents.
Removed planes are skipped. Cost: O(pins + 50), two reads each.

Reconciliation, two flows side by side:

- the lists: drawn again when a list changes or a plane is removed
  (one append to ``Space.indexes.removed``), tiles written in order and the
  ones past the end erased, so the browser keeps them in order;
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
from .common import Compact, page


__all__ = ["TILES", "View", "draw", "out", "read", "shown", "tiles"]


#: Most tiles a group draws, its "+N more" tile included.
TILES = 8


def _live(held: nu.Nu, cap: int | None = None) -> nu.List:
    """The ids of a Web list still in the space, in list order, the first ``cap`` of them."""
    listed = nu.List(nu.If(held.exists(), nu.list(held), []))
    kept = listed.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p))).to_list()
    return nu.List(kept) if cap is None else nu.List(nu.List(kept)[0:cap])


def read() -> nu.Dict:
    """``{pinned, pins, recent}``: the pins to draw, how many pins there are, the recents to draw.

    ``pinned`` holds :data:`TILES` pages when it all fits, else ``TILES - 1``
    and the rest is ``pins`` minus that. Each page is ``{id, title, icon,
    href}``. Bare read, bracket it.
    """
    pins = _live(Web.pinned)
    fits = pins.len() <= TILES
    pinned = nu.List(nu.If(fits, pins, nu.List(pins[0 : TILES - 1])))
    recent = _live(Web.recents, TILES)
    return nu.Dict.of(
        pinned=pinned.iter().map(lambda p: page(nu.Str(p))).to_list(),
        pins=pins.len(),
        recent=recent.iter().map(lambda p: page(nu.Str(p))).to_list(),
    )


# --- The view ------------------------------------------------------------------------------


class GroupHead(nustd.ui.Row):
    """A group's icon, name and count."""

    icon = nustd.ui.IconRef.slot()
    label = nustd.ui.TextRef.slot(size="sm", weight="medium", tone="muted")
    count = nustd.ui.TextRef.slot(size="sm", tone="muted")


class Group(nustd.ui.Column):
    """A group of page tiles."""

    head = GroupHead.slot(gap=2)
    tiles = nustd.ui.GridRef.slot(nustd.ui.PageLinkRef, columns=4, min_width=160, gap=1)
    empty = nustd.ui.TextRef.slot(size="sm", tone="muted")


class Block(nustd.ui.Column):
    """The ``history`` cell's node."""

    title = nustd.ui.HeadingRef.slot(label="History", level=2)
    pinned = Group.slot(gap=1)
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


def _group(
    group: Group, pages: nu.List, more: nu.Int, label: str, icon: str, count: nu.Nu, none: str
) -> nu.Nu:
    """One group: its head, its tiles in order, the rest erased, a "+N more" tile, an empty line."""
    n = pages.len()
    tiles_ = nu.Sequential(
        *[nu.IfDo(n > i, _tile(group, i, pages[i]), tile(group, i).erase()) for i in range(TILES)]
    )
    more_tile = group.tiles["more"]
    extra = nu.IfDo(
        more > 0,
        more_tile.set(
            href="", title=f"more {label.lower()}", icon=nu.Str("+") + nu.Str(Compact(more))
        ),
        more_tile.erase(),
    )
    empty = nu.IfDo(n == 0, group.empty.set(none), group.empty.erase())
    head = (
        group.head.icon.set(icon)
        >> group.head.label.set(label)
        >> group.head.count.set(nu.Str(count))
    )
    # The more tile goes after the tiles: erased first when the tiles grow into its place.
    return head >> nu.IfDo(more == 0, more_tile.erase()) >> tiles_ >> extra >> empty


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`."""
    d = nu.Dict(got)
    view = View.history
    pinned, recent = nu.List(d["pinned"]), nu.List(d["recent"])
    pins = nu.Int(d["pins"])
    return (
        view.title.set("History", level=2)
        >> _group(
            view.pinned,
            pinned,
            pins - pinned.len(),
            "Pinned",
            "pin",
            Compact(pins),
            "Nothing pinned.",
        )
        >> _group(view.recent, recent, nu.Int(0), "Recent", "clock", "", "Nothing opened yet.")
    )


def draw() -> nu.Nu:
    """One read, then its drawing."""
    return nu.let(atomic(read()), show)


# --- Per tile ------------------------------------------------------------------------------


def shown() -> nu.List:
    """The tiles drawn now, as ``"<group>|<index>|<plane>"``: one arm each. Bare read."""

    def keyed(group: str, ids: nu.List) -> list[nu.Nu]:
        return [
            nu.If(ids.len() > i, nu.Str(f"{group}|{i}|") + nu.Str(ids[i]), "") for i in range(TILES)
        ]

    pins = _live(Web.pinned)
    pinned = nu.List(nu.If(pins.len() <= TILES, pins, nu.List(pins[0 : TILES - 1])))
    both = nu.List.of(*keyed("pinned", pinned), *keyed("recent", _live(Web.recents, TILES)))
    return nu.List(both.iter().filter(lambda k: nu.Str(k) != "").to_list())


def tiles(at: nu.Attr) -> nu.Nu:
    """One tile's arm: redraw it when its plane's name or icon changes. Event: a miss is only stale."""
    parts = nu.List(nu.Str(at).split("|", 2))
    group, i, plane = nu.Str(parts[0]), nu.Str(parts[1]), nu.Str(parts[2])
    row = Space.planes[plane]
    changes = nu.OnAny(row.name.on_change(), row.icon.on_change())

    def redraw(group_: Group) -> nu.Nu:
        return nu.let(atomic(page(plane)), lambda got: _tile(group_, i, got))

    body = nu.IfDo(group == "pinned", redraw(View.history.pinned), redraw(View.history.recent))
    return nu.ReactEvery(atomic(changes), body)


def _lists() -> nu.Nu:
    """What moves the lists: a pin or a visit, or a plane removed anywhere."""
    return nu.OnAny(
        Web.pinned.on_change(),
        Web.pinned.on_children_change(),
        Web.recents.on_change(),
        Web.recents.on_children_change(),
        Space.indexes.removed.on_children_change(),
    )


def out() -> nu.Nu:
    """The cell's program: the lists, and one arm per tile drawn."""
    return nu.ParallelAsync(
        nu.Reconcile(atomic(_lists()), draw()),
        nu.ReconcileLatestEach(atomic(shown()), atomic(_lists()), tiles),
    )
