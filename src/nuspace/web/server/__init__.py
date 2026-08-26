"""nuspace-shell -- nuspace's host application on the nu.ui fabric.

Sibling to ``nu.ui.nudle``: another concrete host built on
``nu.ui.core``. Ships a ``Page`` primitive, a ``NuspaceSession`` over
FastAPI ws, ``build_fastapi_app`` for the http stack, and a
``NuspaceServer`` fabric + ``server()`` preset.

Nuspace-specialized refs (LensRef today, AppsExplorerRef /
PagesRendererRef later) live under ``nuspace.web.refs`` and slot onto
``shell.Page`` classes.
"""

from .fabric import NuspaceServer, server
from .page import Page
from .serve import build_fastapi_app
from .session import NuspaceSession, Subscription


__all__ = [
    "NuspaceServer",
    "NuspaceSession",
    "Page",
    "Subscription",
    "build_fastapi_app",
    "server",
]
