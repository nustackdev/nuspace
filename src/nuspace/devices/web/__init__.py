"""The web device: the browser's way into the space, with its own stores.

- :mod:`.shapes`: :class:`Web` (web planes, pins, recents) and
  :class:`Conn` (browser tabs, their panes and sidebar folds).
- :mod:`.stores`: their files, channels and init terms.
"""

from .shapes import Conn, Web
from .stores import CONN_STORE, WEB_STORE


__all__ = ["CONN_STORE", "WEB_STORE", "Conn", "Web"]
