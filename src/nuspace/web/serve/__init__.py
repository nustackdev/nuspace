"""nuspace.web.serve -- transport and chrome. Below the fabric, not part of it.

Module layout:

- :mod:`.shell`   -- ``Screen`` / ``Shell``, the fixed top-level routes as
  nustd.ui Shapes. Chrome only; the page tree lives in kv.
- :mod:`.session` -- ``NuspaceSession``, a ``nustd.ui`` Session over one websocket.
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
from .shell import Screen, ScreenRef, Shell


__all__ = [
    "NuspaceServer",
    "NuspaceSession",
    "Screen",
    "ScreenRef",
    "Shell",
    "Subscription",
    "build_fastapi_app",
    "server",
]
