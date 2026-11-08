"""The web device's two stores: Web (web planes, pins, recents) and Conn (browser tabs).

Each its own root and tag, in its own file under ``devices/web/``, so a
space opened without the web device carries no web data. Core never reads
them; they name plane and plane run ids only::

    Web                                  web_state.db, persistent
      planes[plane_id]                   WebPlane: editable, full_width, compact
      pinned                             [plane id], user order
      recents                            [plane id], most recent first, capped

    Conn                                 conn.db, made fresh at every open
      connections[sid]                   Tab
        order                            [plane id], the panes left to right
        panes[plane_id]                  Pane: params, plane_run, restart
        expanded[plane_id]               sidebar folds open in this tab
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["RECENTS_CAP", "Conn", "Pane", "Tab", "Web", "WebPlane"]


#: How many plane ids ``Web.recents`` keeps. Past it the oldest drops.
RECENTS_CAP = 50


class WebPlane(nu.Shape):
    """A plane on the web: its row at ``Web.planes[id]``.

    The row existing is the fact: the sidebar and pins list the plane, and a
    tab opening it runs it with the session wrapper. Planes with no row
    (services, searches) are not on the web. The flags are how it shows:
    ``editable`` (its cells can be edited), ``full_width``, ``compact``.
    """

    editable = nustd.kv.BoolRef.slot()
    full_width = nustd.kv.BoolRef.slot()
    compact = nustd.kv.BoolRef.slot()


class Web(nu.Shape):
    """The root of ``web_state.db``, and its store's tag.

    ``planes`` is every web plane by plane id. ``pinned`` is the pinned
    plane ids in the user's order. ``recents`` is plane ids, most recent
    first, at most :data:`RECENTS_CAP`. Both are small user lists. A removed
    plane keeps its entries; readers skip it.
    """

    planes = nustd.kv.DictRef.slot(WebPlane)
    pinned = nustd.kv.ListRef.slot(str)
    recents = nustd.kv.ListRef.slot(str)


class Pane(nu.Shape):
    """One open pane of a tab: ``Conn.connections[sid].panes[plane_id]``.

    ``params`` is what the pane's cells read as their own, str to str,
    written whole. ``plane_run`` is the plane run nav keeps for the pane.
    ``restart`` is a token: a new one asks nav to restart that run.
    """

    params = nustd.kv.PrimitiveDictRef.slot()
    plane_run = nustd.kv.StrRef.slot()
    restart = nustd.kv.StrRef.slot()


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
