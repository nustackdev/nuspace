"""nuspace.web -- the browser-facing side: refs, transport, and the driver.

Package layout:

- :mod:`.refs`  -- the nu.ui Refs nuspace ships (``PagesRef``, ``NavRef``).
- :mod:`.serve` -- all the python that runs them: shell, session, FastAPI app,
  uvicorn fabric, and the reactive composition.
- ``ui/``       -- the browser bundle, which speaks the same wire.

Transport sits below the fabric: a session is one browser connection, not a Nu
concept. The refs and the reactive driver are what nuspace actually says.
"""

from __future__ import annotations

from .refs import NavRef, PagesRef
from .serve import (
    NuspaceServer,
    NuspaceSession,
    Screen,
    Screens,
    Shell,
    Subscription,
    build_fastapi_app,
    pages_driver,
    server,
)


__all__ = [
    "NavRef",
    "NuspaceServer",
    "NuspaceSession",
    "PagesRef",
    "Screen",
    "Screens",
    "Shell",
    "Subscription",
    "build_fastapi_app",
    "pages_driver",
    "server",
]
