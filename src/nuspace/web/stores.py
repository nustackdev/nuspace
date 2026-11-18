"""The web device's stores: their roots and inits, and Conn's reset.

    Web    persistent: web planes, recents, desks, roles
    Conn   per web start: browser tabs, cleared by one commit when web starts

Where each lives (a file, a channel) is an assembly's call
(``nuspace.space.local.layout``). Bound at every open, served or headless
(the web device's driver runs only when served), so a web row a program
writes always lands. Their init terms are bare, as the core ones are
(:mod:`nuspace.shapes.stores`): the caller brackets each store on its own.
"""

from __future__ import annotations

import nu
from nuspace.shapes import Store

from .shapes import Conn, Web


__all__ = ["CONN_STORE", "WEB_STORE", "init_conn", "init_web", "reset_conn"]


def init_web() -> nu.Nu:
    """The Web store ready: web planes, recents, desks and roles made where missing."""
    return (
        Web.planes.init(nu.Dict.create())
        >> Web.recents.init(nu.List.create())
        >> Web.desks.init(nu.Dict.create())
        >> Web.roles.init(nu.Dict.create())
    )


def init_conn() -> nu.Nu:
    """The Conn store ready: the connections dict made where missing."""
    return Conn.connections.init(nu.Dict.create())


def reset_conn() -> nu.Nu:
    """Conn emptied: every tab of a web that is gone dropped. Bare, one commit when bracketed.

    No tab outlives the web serving it, so web clears Conn as it starts.
    A commit on the store, never a deleted file: a worker may hold it open.
    """
    return Conn.connections.set(nu.Dict.create())


#: Web planes, recents, desks, roles.
WEB_STORE = Store(Web, init_web)

#: Browser tabs: their panes and sidebar folds.
CONN_STORE = Store(Conn, init_conn)
