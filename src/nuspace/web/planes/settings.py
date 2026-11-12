"""Settings: the space's own settings plane. Made at open when missing (:mod:`nuspace.web.planes`).

Like home (:mod:`..home`): a system web plane the ``settings`` role names, made once,
its cells the owner's after that. The sidebar's nav row and Cmd+, are the
way to it. One cell, ``settings``, a shim over this module (:func:`out`),
so a fix here shows on the next open of any space made with it.

A page of sections, each a titled card of labelled values:

- Space: name, store format, location, created, up since this open;
- Software: the nuspace and nu versions this process runs, docs and source;
- Navigation: the planes the nav row opens, as links, with their keys;
- Kept elsewhere: what is not the space's (theme, telemetry), and where it is.

Only what belongs to the space lives here. What belongs to one device or
browser, eg its theme, stays there, and what belongs to the user, eg
telemetry, lives in ``~/.nuspace`` (``nuspace telemetry``). Nothing draws on
a timer: the cell draws again when ``Space.info`` or the roles change, and
time moving on its own (age, uptime) ticks in the browser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from ..home import common
from ..home.common import SpaceName, SpaceWhere
from ..ops import page
from ..shapes import Web


if TYPE_CHECKING:
    from nustd.ui.core import ItemRef


__all__ = ["CELLS", "ICON", "NAME", "View", "draw", "out", "read", "show"]


#: What the plane is called.
NAME = "Settings"

#: Its icon.
ICON = "emoji:⚙️"

#: The cells settings is made with, in order, as ``(name, source)``.
CELLS = (("settings", "from nuspace.web.planes.settings import out\n"),)

DOCS = "https://nustack.dev/docs"
SOURCE = "https://github.com/nustackdev/nuspace"

#: The nav row's planes: ``(role, what it is, its keys)``, in the sidebar's order.
NAV = (
    ("home", "A live pulse of the space", ["mod", "shift", "H"]),
    ("search", "Find content across the space", ["mod", "K"]),
    ("settings", "This page", ["mod", ","]),
)


#: The versions this process runs, read once at import (:data:`..home.common.VERSIONS`).
VERSIONS = {label: v or "not installed" for label, v in common.VERSIONS.items()}


# --- The read ------------------------------------------------------------------------------


def read() -> nu.Dict:
    """What the cell shows, one bare read: ``{path, format, created_at, opened_at, nav}``.

    ``nav`` is a page (``{id, title, icon, href}``) per role in :data:`NAV`
    order, ``{}`` for a role not set. Cost: 4 reads plus 3 per role.
    """
    info = Space.info

    def nav(role: str) -> nu.Nu:
        plane = nu.Str(Web.roles[role].fallback(""))
        return nu.If(plane == "", nu.Dict.of(), page(plane))

    return nu.Dict.of(
        path=info.path.fallback(""),
        format=info.format.fallback(0),
        created_at=info.created_at.fallback(0.0),
        opened_at=info.opened_at.fallback(0.0),
        nav=nu.List.of(*(nav(role) for role, _, _ in NAV)),
    )


# --- The view ------------------------------------------------------------------------------


class Page(ui.Column):
    """The ``settings`` cell's node: one section per group, a card each, a hairline between them as on home."""

    space = ui.PageSectionRef.slot(title="Space", description="This space, and where it lives")
    software = ui.PageSectionRef.slot(
        title="Software", description="What the process serving this space runs"
    )
    navigation = ui.PageSectionRef.slot(
        title="Navigation", description="The planes the sidebar's nav row opens, from anywhere"
    )
    elsewhere = ui.PageSectionRef.slot(
        title="Kept elsewhere", description="Settings that are not the space's, and where they are"
    )


class View(nu.Shape):
    """The ``settings`` cell's root."""

    settings = Page.slot(gap=6, divided=True)


page_ = View.settings


def _board(section: ui.PageSectionRef, **props: object) -> ui.GridRef:
    """A section's card, its body a two column board of fields; one column on a narrow pane."""
    card = section[0].to(ui.CardRef.slot(size="sm"))
    return card[0].to(ui.GridRef.slot(cols=2, gap=5, stack_below=480, **props))


def _field(cell: ItemRef, label: str, help: str = "") -> ui.FieldRef:
    return cell.to(ui.FieldRef.slot(label=label, help=help))


# Space
space = _board(page_.space, span={(1, 0): 2})  # location: two columns
name = _field(space[0, 0], "Name").control.to(ui.TextRef.slot(weight="medium"))
store_format = _field(space[0, 1], "Store format").control.to(ui.TextRef.slot(mono=True))
location = _field(space[1, 0], "Location", "The space directory: space.db and its stores")
where = location.control.to(ui.TextRef.slot(mono=True, size="sm"))
created = _field(space[2, 0], "Created").control.to(ui.RelativeTimeRef)
up = _field(space[2, 1], "Up", "Since this open").control.to(
    ui.RelativeTimeRef.slot(mode="duration")
)

# Software
software_card = page_.software[0].to(ui.CardRef.slot(size="sm"))
software = software_card[0].to(ui.GridRef.slot(cols=2, gap=5, stack_below=480))
versions = {
    dist: _field(software[0, i], dist).control.to(ui.TextRef.slot(mono=True))
    for i, dist in enumerate(VERSIONS)
}
docs = software_card.footer[0].to(ui.LinkRef.slot(target="_blank", icon="book-open"))
source = software_card.footer[1].to(ui.LinkRef.slot(target="_blank", icon="github"))

# Navigation: the card stacks the rows itself
nav_list = page_.navigation[0].to(ui.CardRef.slot(size="sm", gap=1))


def _nav_row(role: str) -> ui.RowRef:
    return nav_list[role].to(ui.RowRef.slot(gap=3, grow={0: 1}))


# Kept elsewhere
elsewhere = _board(page_.elsewhere)
theme = _field(elsewhere[0, 0], "Theme", "Flip it from the sidebar's footer").control.to(ui.TextRef)
telemetry = _field(elsewhere[0, 1], "Telemetry", "Per user, kept in ~/.nuspace").control.to(
    ui.TextRef.slot(mono=True, size="sm")
)


def _nav(i: int, got: nu.Nu) -> nu.Nu:
    """The nav row of :data:`NAV` ``i``: a link to its plane and its keys, erased when unset."""
    role, what, keys = NAV[i]
    d = nu.Dict(got)
    row = _nav_row(role)
    return nu.IfDo(
        d.contains("href"),
        row[0]
        .to(ui.PageLinkRef)
        .set(href=d["href"], title=d["title"], icon=d["icon"], description=what)
        >> row[1].to(ui.ShortcutRef.slot(variant="ghost", size="sm")).set(keys),
        row.erase(),
    )


def show(got: nu.ObjectRef) -> nu.Nu:
    """Draw one read of :func:`read`. Writes only what the read says, no clock."""
    d = nu.Dict(got)
    path = nu.Str(d["path"])
    created_at = nu.Float(d["created_at"])
    opened_at = nu.Float(d["opened_at"])
    nav = nu.List(d["nav"])
    return nu.Sequential(
        name.set(SpaceName(path)),
        store_format.set(nu.str(d["format"])),
        where.set(nu.If(path == "", "Not on disk: closing it drops it", SpaceWhere(path))),
        nu.IfDo(created_at > 0, created.set(created_at * 1000)),
        nu.IfDo(opened_at > 0, up.set(opened_at * 1000, mode="duration")),
        *(v.set(VERSIONS[dist]) for dist, v in versions.items()),
        docs.set(href=DOCS, label="Docs"),
        source.set(href=SOURCE, label="Source"),
        *(_nav(i, nav[i]) for i in range(len(NAV))),
        theme.set("Per browser"),
        telemetry.set("nuspace telemetry"),
    )


def draw() -> nu.Nu:
    """One read, then its drawing."""
    return nu.let(atomic(read()), show)


def out() -> nu.Nu:
    """The cell's program: draw, then again whenever the space's info or the roles move."""
    changes = nu.OnAny(Space.info.on_children_change(), Web.roles.on_children_change())
    return nu.Reconcile(atomic(changes), draw())
