"""``nuspace.devices.web``: the web device, the browser's way into the space, with its own stores.

The sdk, what a program calls, is the ops (:mod:`.ops`), flat here::

    import nuspace.devices.web as web

    nuspace.atomic(web.add(plane, editable=True))     # put a plane on the web
    web.params(), web.on_params()                     # a cell's own pane params
    web.restart_cell(sid, cell)                       # run one cell again, brackets itself
    nuspace.atomic(web.link(row.link, plane))         # draw a link to a plane
    nuspace.atomic(web.set_role("home", plane))       # make a plane the home

- :mod:`.shapes`: :class:`Web` (web planes, recents, desks, roles) and :class:`Conn`
  (browser tabs, their panes and sidebar folds); :mod:`.stores`: their
  files, channels and init terms.
- :mod:`.ops`: the ops over them, all but the desks'.
- :mod:`.desks`: the desks: their ops (``web.desks.set_desk``, ...), the
  browser node and feed, the desk pruner.
- :mod:`.home`: Home and the home indexer; :mod:`.planes`: every plane
  the device ships with, made at open (search and settings live there).
- :mod:`.nav`: the driver running what the panes show.
- :mod:`.device`: the server and one arm per tab, the sidebar, viewer and
  desks feeds under it.
  Imported by the host only: it pulls in the web server.

Safe for a worker to import: nothing imported here pulls in a server.
"""

from . import desks
from .ops import (
    add,
    close_tab,
    collapse,
    expand,
    href,
    link,
    on_params,
    open_tab,
    params,
    restart_cell,
    restart_pane,
    set,
    set_pane_params,
    set_panes,
    set_role,
    visit,
)
from .shapes import RECENTS_CAP, ROLES, Conn, Pane, Tab, Web, WebPlane
from .stores import CONN_STORE, WEB_STORE


__all__ = [
    "CONN_STORE",
    "RECENTS_CAP",
    "ROLES",
    "WEB_STORE",
    "Conn",
    "Pane",
    "Tab",
    "Web",
    "WebPlane",
    "add",
    "close_tab",
    "collapse",
    "desks",
    "expand",
    "href",
    "link",
    "on_params",
    "open_tab",
    "params",
    "restart_cell",
    "restart_pane",
    "set",
    "set_pane_params",
    "set_panes",
    "set_role",
    "visit",
]
