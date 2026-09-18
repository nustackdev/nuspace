"""What the web driver assembles.

The chrome and the connection, and nothing that decides anything. A browser
tab gets a Shell, which is the slots a tab holds before a single Plane is
drawn; a connection gets a Session, which is how this process and a worker
both reach that tab; and a surface gets built out of the wire idiom and the
arms in :mod:`nuspace.web.utils`.

Which Planes are up and what they are drawn on is a driver's call, one level
up in :mod:`nuspace.drivers`.
"""

from nuspace.web.nav import PLANE_ID, TOP, Nav, NavRef, opened, opens, per_connection
from nuspace.web.session import HostedSession, Sessions, WsSession, served_sessions
from nuspace.web.shell import Boot, NuspaceShell, PagesScreen, Screen, ScreenRef, Shell
from nuspace.web.utils import (
    OPS,
    Arms,
    ChannelRef,
    SpaceRef,
    event,
    field_ids,
    field_index,
    field_str,
    write,
)


__all__ = [
    "OPS",
    "PLANE_ID",
    "TOP",
    "Arms",
    "Boot",
    "ChannelRef",
    "HostedSession",
    "Nav",
    "NavRef",
    "NuspaceShell",
    "PagesScreen",
    "Screen",
    "ScreenRef",
    "Sessions",
    "Shell",
    "SpaceRef",
    "WsSession",
    "event",
    "field_ids",
    "field_index",
    "field_str",
    "opened",
    "opens",
    "per_connection",
    "served_sessions",
    "write",
]
