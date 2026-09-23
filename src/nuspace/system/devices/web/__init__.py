"""The web device: the browser shell, its feeds, and the session env.

- :mod:`.shell`: the frame a tab holds, the sidebar and the viewer.
- :mod:`.sidebar`, :mod:`.viewer`: each region's ref, wire vocabulary and
  feed.
- :mod:`.session`: how a worker reaches a connection, and the host's book.
- :mod:`.env`: the session env factory (D17).
- :mod:`.device`: :func:`serve_web`, the term and the envs to register.

Everything here but :mod:`.device` is safe for a worker to import: a
drawing run's body holds refs from this package, and unpickling it imports
them. :mod:`.device` reaches the ws server, which imports uvicorn and
fastapi, so it is loaded only when :func:`serve_web` is asked for.
"""

from typing import Any

from nuspace.system.devices.web.env import SESSION_ENV, SessionWrap, session_env
from nuspace.system.devices.web.session import (
    SESSION_ATTR,
    ConnectedSession,
    Connections,
    FrameCodec,
    HostedSession,
    Sessions,
    proxied_session,
    served_sessions,
)
from nuspace.system.devices.web.shell import Boot, Shell
from nuspace.system.devices.web.sidebar import SidebarRef, sidebar_feed
from nuspace.system.devices.web.utils import CELLS, CellRoot, SpaceRef, cell_ui, cells_ui
from nuspace.system.devices.web.viewer import ViewerRef, viewer_feed


__all__ = [
    "BANNER",
    "CELLS",
    "SESSION_ATTR",
    "SESSION_ENV",
    "Boot",
    "CellRoot",
    "ConnectedSession",
    "Connections",
    "FrameCodec",
    "HostedSession",
    "SessionWrap",
    "Sessions",
    "Shell",
    "SidebarRef",
    "SpaceRef",
    "ViewerRef",
    "cell_ui",
    "cells_ui",
    "connection",
    "proxied_session",
    "serve_web",
    "served_sessions",
    "session_env",
    "sidebar_feed",
    "viewer_feed",
]

_DEVICE = {"BANNER", "connection", "serve_web"}


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Load :mod:`.device` on first use: it imports the web server."""
    if name in _DEVICE:
        from nuspace.system.devices.web import device

        return getattr(device, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
