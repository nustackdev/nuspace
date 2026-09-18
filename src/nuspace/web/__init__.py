"""What the web driver assembles.

The frame, the two regions and the connection, and nothing that decides
anything. A browser tab gets a Shell, which is the slots a tab holds before a
single Plane is drawn; it gets a sidebar, which is every Plane that draws; it
gets a Viewer, which is whichever of them the sidebar picked; a connection gets
a Session, which is how this process and a worker both reach that tab; and both
regions are built out of the wire idiom and the arms in
:mod:`nuspace.web.utils`.

Which Planes are up and what they are drawn on is a driver's call, one level up
in :mod:`nuspace.drivers`.
"""

from nuspace.web.route import PLANE_ID, Route, RouteRef, opened, opens, per_connection
from nuspace.web.session import HostedSession, Sessions, WsSession, served_sessions
from nuspace.web.shell import Boot, Shell
from nuspace.web.sidebar import ROOT_ID, SidebarRef, rows, sidebar_driver
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
from nuspace.web.viewer import ViewerRef, viewer_driver


__all__ = [
    "OPS",
    "PLANE_ID",
    "ROOT_ID",
    "Arms",
    "Boot",
    "ChannelRef",
    "HostedSession",
    "Route",
    "RouteRef",
    "Sessions",
    "Shell",
    "SidebarRef",
    "SpaceRef",
    "ViewerRef",
    "WsSession",
    "event",
    "field_ids",
    "field_index",
    "field_str",
    "opened",
    "opens",
    "per_connection",
    "rows",
    "served_sessions",
    "sidebar_driver",
    "viewer_driver",
    "write",
]
