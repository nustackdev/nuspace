"""The web device's two stores: Web (web planes, recents, desks, roles) and Conn (browser tabs).

Each its own root and tag, in its own file under ``devices/web/``, so a
space opened without the web device carries no web data. Core never reads
them; they name plane and plane run ids only::

    Web                                  web_state.db, persistent
      planes[plane_id]                   WebPlane: editable, width
      recents                            [plane id], most recent first, capped
      desks[desk_id]                     Desk, in sidebar order
        name                             the desk's name
        entries[item_id]                 plane item or strip, in desk order
      desks_seeded                       True once Favorites was seeded
      roles[role]                        plane id: home, settings, search

    Conn                                 conn.db, made fresh at every open
      connections[sid]                   Tab
        order                            [plane id], the panes left to right
        panes[plane_id]                  Pane: params, plane_run, restart
        expanded[plane_id]               sidebar folds open in this tab
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["RECENTS_CAP", "ROLES", "WIDTHS", "Conn", "Desk", "Pane", "Tab", "Web", "WebPlane"]


#: How many plane ids ``Web.recents`` keeps. Past it the oldest drops.
RECENTS_CAP = 50

#: The jobs a plane fills for the shell, the keys of ``Web.roles``: the nav
#: section's rows, ``/`` (home) and Cmd+K (search) resolve through them.
ROLES = ("home", "settings", "search")

#: How wide a web plane's content runs in its pane, ``WebPlane.width``: the
#: most it takes, never more than the pane. ``page`` is the reading measure,
#: ``board`` a dashboard's, ``full`` the whole pane. The browser draws them.
WIDTHS = ("page", "board", "full")


class WebPlane(nu.Shape):
    """A plane on the web: its row at ``Web.planes[id]``.

    The row existing is the fact: the sidebar lists the plane, and a
    tab opening it runs it with the session wrapper. Planes with no row
    (services, searches) are not on the web. The flags are how it shows:
    ``editable`` (its cells can be edited) and ``width`` (one of
    :data:`WIDTHS`, ``page`` when unset).
    """

    editable = nustd.kv.BoolRef.slot()
    width = nustd.kv.StrRef.slot()


class Desk(nu.Shape):
    """A desk: ``Web.desks[desk_id]``. A named, ordered collection of items.

    ``entries`` is every item by item id, in the desk's order: each a plain
    dict read and written whole, a plane item ``{kind: "plane", original,
    recent?}`` or a strip ``{kind: "strip", columns}``. The id is the key,
    never in the value. The slot is ``entries`` because a shape ref has
    ``items`` of its own; the vocab and the ops say item.
    """

    name = nustd.kv.StrRef.slot()
    entries = nustd.kv.OrderedDictRef.slot(nustd.kv.PrimitiveDictRef)


class Web(nu.Shape):
    """The root of ``web_state.db``, and its store's tag.

    ``planes`` is every web plane by plane id. ``recents`` is plane ids,
    most recent first, at most :data:`RECENTS_CAP`, a small list. A removed
    plane keeps its entries; readers skip it.

    ``desks`` is every desk by desk id (:class:`Desk`), ordered: the order
    the sidebar draws them in, set by placement, not by id.
    ``desks_seeded`` is set once the Favorites desk was made, so closing it
    never brings it back. ``roles``
    is the plane id each of :data:`ROLES` resolves to, seeded with the
    system planes; set and changed, never removed.
    """

    planes = nustd.kv.DictRef.slot(WebPlane)
    recents = nustd.kv.ListRef.slot(str)
    desks = nustd.kv.OrderedDictRef.slot(Desk)
    desks_seeded = nustd.kv.BoolRef.slot()
    roles = nustd.kv.DictRef.slot(str)


class Pane(nu.Shape):
    """One open pane of a tab: ``Conn.connections[sid].panes[plane_id]``.

    ``params`` is what the pane's cells read as their own, str to str,
    written whole. ``plane_run`` is the plane run nav keeps for the pane.
    ``restart`` is a token: a new one asks nav to restart that run.
    ``opened`` is a token minted when the pane opens, never changed after:
    a pane closed and opened again is a new open, even when the tab's order
    reads the same before and after (the viewer keys its arms on it).
    """

    params = nustd.kv.PrimitiveDictRef.slot()
    plane_run = nustd.kv.StrRef.slot()
    restart = nustd.kv.StrRef.slot()
    opened = nustd.kv.StrRef.slot()


class Tab(nu.Shape):
    """One browser tab: ``Conn.connections[sid]``.

    ``order`` is its panes' plane ids left to right, rewritten whole as the
    browser sends it. ``panes`` holds each open pane's data by plane id, so
    nav and params write one pane without touching the order. ``expanded``
    is the plane ids whose sidebar branch is open in this tab.
    """

    order = nustd.kv.ListRef.slot(str)
    panes = nustd.kv.DictRef.slot(Pane)
    expanded = nustd.kv.DictRef.slot(bool)


class Conn(nu.Shape):
    """The root of ``conn.db``, and its store's tag. Deleted and made fresh at every open."""

    connections = nustd.kv.DictRef.slot(Tab)
