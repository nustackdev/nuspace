"""``nuspace.devices.web``: the web device, the browser's way into the space, with its own stores.

The sdk, what a program calls, is the ops (:mod:`.ops`), flat here::

    import nuspace.devices.web as web

    nuspace.atomic(web.add(plane, editable=True))     # put a plane on the web
    nuspace.atomic(web.pin(plane))                    # pin it in the sidebar
    web.params(), web.on_params()                     # a cell's own pane params
    nuspace.atomic(web.link(row.link, plane))         # draw a link to a plane

- :mod:`.shapes`: :class:`Web` (web planes, pins, recents) and :class:`Conn`
  (browser tabs, their panes and sidebar folds); :mod:`.stores`: their
  files, channels and init terms.
- :mod:`.ops`: the ops over them.
- :mod:`.nav`: the driver running what the panes show.
- :mod:`.device`: the server and one arm per tab, the sidebar and viewer
  feeds under it, and :mod:`.planes` (home, settings, search) it ships with.
  Imported by the host only: it pulls in the web server.

Safe for a worker to import: nothing imported here pulls in a server.
"""

from .ops import (
    add,
    close_tab,
    collapse,
    expand,
    href,
    link,
    move_pin,
    on_params,
    open_tab,
    params,
    pin,
    restart_pane,
    set,
    set_pane_params,
    set_panes,
    unpin,
    visit,
)
from .shapes import RECENTS_CAP, Conn, Pane, Tab, Web, WebPlane
from .stores import CONN_STORE, WEB_STORE


__all__ = [
    "CONN_STORE",
    "RECENTS_CAP",
    "WEB_STORE",
    "Conn",
    "Pane",
    "Tab",
    "Web",
    "WebPlane",
    "add",
    "close_tab",
    "collapse",
    "expand",
    "href",
    "link",
    "move_pin",
    "on_params",
    "open_tab",
    "params",
    "pin",
    "restart_pane",
    "set",
    "set_pane_params",
    "set_panes",
    "unpin",
    "visit",
]
