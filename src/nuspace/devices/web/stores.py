"""The web device's stores, beside the core ones in the space's data dir.

Files, roots and channels::

    devices/web/web_state.db   Web    nuspace.web    persistent
    devices/web/conn.db        Conn   nuspace.conn   deleted and made fresh at every open

Opened only when the web device is on. Their init terms are bare, as the
core ones are (:mod:`nuspace.host.stores`): the caller brackets each store
on its own.
"""

from __future__ import annotations

import nu
from nuspace.shapes import Store

from .shapes import Conn, Web


__all__ = ["CONN_STORE", "WEB_STORE", "init_conn", "init_web"]


def init_web() -> nu.Nu:
    """``web_state.db`` ready: web planes, pins and recents made where missing."""
    return (
        Web.planes.init(nu.Dict.create())
        >> Web.pinned.init(nu.List.create())
        >> Web.recents.init(nu.List.create())
    )


def init_conn() -> nu.Nu:
    """``conn.db`` ready: the connections dict made where missing."""
    return Conn.connections.init(nu.Dict.create())


#: Web planes, pins, recents.
WEB_STORE = Store(Web, "devices/web/web_state.db", "nuspace.web", init_web)

#: Browser tabs: their panes and sidebar folds.
CONN_STORE = Store(Conn, "devices/web/conn.db", "nuspace.conn", init_conn)
