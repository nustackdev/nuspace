"""nuspace.web -- the browser-facing side: refs, drivers, transport, assembly.

Package layout, per domain rather than per kind. A surface's ref and the
driver that works it are one thing and sit in one place:

- :mod:`.apps`  -- ``AppsRef`` + ``apps_driver``.
- :mod:`.pages` -- ``PagesRef`` + ``pages_driver``.
- :mod:`.nav`   -- ``NavRef``, where the browser is. Shared by both, owned by
  neither. Readable, never written.
- :mod:`.wire`  -- how a surface ref addresses events and writes.
- :mod:`.arms`  -- how a driver builds one arm, and reads one event's fields.
- :mod:`.space` -- the assembly: both surfaces on one shell, both drivers in
  one tree. The only module that knows both domains exist.
- :mod:`.serve` -- transport and chrome: shell, session, FastAPI app, uvicorn.
- ``ui/``       -- the browser bundle, which speaks the same wire.

Transport sits below the fabric: a session is one browser connection, not a Nu
concept. The refs and the drivers are what nuspace actually says.
"""

from __future__ import annotations

from .apps import AppsRef, apps_driver
from .nav import NavRef
from .pages import PagesRef, pages_driver
from .serve import (
    NuspaceServer,
    NuspaceSession,
    Screen,
    Screens,
    Shell,
    Subscription,
    build_fastapi_app,
    server,
)
from .space import AppsScreen, NuspaceShell, PagesScreen, space_driver


__all__ = [
    "AppsRef",
    "AppsScreen",
    "NavRef",
    "NuspaceServer",
    "NuspaceSession",
    "NuspaceShell",
    "PagesRef",
    "PagesScreen",
    "Screen",
    "Screens",
    "Shell",
    "Subscription",
    "apps_driver",
    "build_fastapi_app",
    "pages_driver",
    "server",
    "space_driver",
]
