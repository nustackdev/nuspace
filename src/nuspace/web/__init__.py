"""nuspace.web -- the browser-facing side: refs, drivers, transport, assembly.

Package layout, per domain rather than per kind. A surface's ref and the
driver that works it are one thing and sit in one place:

- :mod:`.apps`  -- ``AppsRef`` + ``apps_driver``.
- :mod:`.pages` -- ``PagesRef`` + ``pages_driver``.
- :mod:`.lens`  -- ``LensRef`` + ``lens_driver``. Read-only, store-less: it
  browses whatever Shape it is pointed at.
- :mod:`.nav`   -- ``NavRef``, where the browser is. Shared, owned by nobody.
  Readable, never written, and only the pages driver reads it.
- :mod:`.wire`  -- how a surface ref addresses events and writes.
- :mod:`.arms`  -- how a driver builds one arm, and reads one event's fields.
- :mod:`.space` -- the assembly: every surface on one shell, every driver in
  one tree. The only module that knows all the domains exist.
- :mod:`.serve` -- transport and chrome: shell, session, FastAPI app, uvicorn.
- ``ui/``       -- the browser bundle, which speaks the same wire.

Transport sits below the fabric: a session is one browser connection, not a Nu
concept. The refs and the drivers are what nuspace actually says.
"""

from __future__ import annotations

from .apps import AppsRef, apps_driver
from .lens import LensRef, lens_driver
from .nav import NavRef
from .pages import PagesRef, pages_driver
from .pages.session import page_session
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
from .space import (
    AppsScreen,
    LensScreen,
    NuspaceShell,
    PagesScreen,
    session_driver,
    space_driver,
    space_tree,
)


__all__ = [
    "AppsRef",
    "AppsScreen",
    "LensRef",
    "LensScreen",
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
    "lens_driver",
    "page_session",
    "pages_driver",
    "server",
    "session_driver",
    "space_driver",
    "space_tree",
]
