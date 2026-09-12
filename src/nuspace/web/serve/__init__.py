"""nuspace.web.serve -- transport and chrome. Below the fabric, not part of it.

Module layout:

- :mod:`.shell`   -- ``Screen`` / ``Screens`` / ``Shell``, the fixed top-level
  routes as nu.ui Shapes. Chrome only; the page tree lives in kv.
- :mod:`.session` -- ``NuspaceSession``, a ``nu.ui`` Session over one websocket.
- :mod:`.app`     -- the FastAPI app and the ``/ws`` endpoint.
- :mod:`.fabric`  -- ``NuspaceServer``, uvicorn wrapped as a ``Provide`` bracket.

Transport and chrome only. What nuspace actually *says* over that transport is
the per-domain refs and drivers in :mod:`nuspace.web.apps` and
:mod:`nuspace.web.pages`, and the browser bundle under ``web/ui``.
"""

from __future__ import annotations

from .app import build_fastapi_app
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
    "server",
]
