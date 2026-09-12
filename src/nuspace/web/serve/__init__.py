"""nuspace.web.serve -- transport, chrome, and the reactive composition.

Module layout:

- :mod:`.shell`   -- ``Screen`` / ``Screens`` / ``Shell``, the fixed top-level
  routes as nu.ui Shapes. Chrome only; the page tree lives in kv.
- :mod:`.session` -- ``NuspaceSession``, a ``nu.ui`` Session over one websocket.
- :mod:`.app`     -- the FastAPI app and the ``/ws`` endpoint.
- :mod:`.fabric`  -- ``NuspaceServer``, uvicorn wrapped as a ``Provide`` bracket.
- :mod:`.driver`  -- the pages driver: one ``ReactForever`` arm per interaction.

Everything here is python. The nuspace-shipped nu.ui Refs are next door in
:mod:`nuspace.web.refs`, and the browser bundle under ``web/ui``.
"""

from __future__ import annotations

from .app import build_fastapi_app
from .driver import pages_driver
from .fabric import NuspaceServer, server
from .session import NuspaceSession, Subscription
from .shell import Screen, Screens, Shell


__all__ = [
    "NuspaceServer",
    "NuspaceSession",
    "Screen",
    "Screens",
    "Shell",
    "Subscription",
    "build_fastapi_app",
    "pages_driver",
    "server",
]
