"""Space: the world. What you open."""

from __future__ import annotations

import nu
import nustd.kv

from .connection import Connection
from .kernel import Kernel
from .plane import Plane
from .tree import Node


__all__ = ["RECENTS_CAP", "Space", "SpaceInfo", "SpaceSettings", "SpaceState"]


#: How many plane ids ``SpaceState.recents`` keeps.
RECENTS_CAP = 20


class SpaceInfo(nu.Shape):
    """What the host says about the space it opened. Written once per open.

    ``path`` is the store directory, ``""`` for a throwaway one. ``opened``
    is when this open started, in seconds since the epoch. ``versions`` maps
    a package name (``nuspace``, and ``nuverse`` when installed) to its
    installed version.
    """

    path = nustd.kv.StrRef.slot()
    opened = nustd.kv.FloatRef.slot()
    versions = nustd.kv.DictRef.slot(str)


class SpaceState(nu.Shape):
    """Space wide state: things about the space as a whole, not one plane.

    ``recents`` is the plane ids opened in a tab, newest first, deduped and
    capped at :data:`RECENTS_CAP`, written whole (D24) by the web device.
    ``info`` is written by the host at open.
    """

    recents = nustd.kv.PrimitiveListRef.slot()
    info = nustd.kv.ShapeRef.slot(SpaceInfo)


class SpaceSettings(nu.Shape):
    """The space's own settings, written from the settings plane. Unset reads as off.

    ``telemetry`` is whether the space may share anonymous usage data.
    Nothing reads it yet: it is wired to telemetry once there is some.

    Space level only: what belongs to one device or browser, eg its theme,
    stays there and never lands in the store.
    """

    telemetry = nustd.kv.BoolRef.slot()


class Space(nu.Shape):
    """Planes, the tree between them, the kernel's records, device and space state.

    ``planes`` is flat, so a plane is one lookup away and a route addresses it
    directly. Nesting is ``tree``, keyed by plane id plus
    :data:`~nuspace.shapes.tree.ROOT`.

    One writer per subtree: people, cells and services write ``planes`` and
    ``tree`` through ops, the kernel writes ``kernel``, the web device writes
    ``connections`` and ``state.recents``, the host writes ``state.info``,
    the settings plane writes ``settings``.

    ``pinned`` is the plane ids pinned to the top of the sidebar, in order,
    written through the pin ops. A pin is a shortcut: the plane stays where
    it is in ``tree``.

    ``Space`` is also the store's tag. kv refs find their navigator by root
    shape class, so the store is bound under this class and anything rerooted
    under it resolves there.
    """

    planes = nustd.kv.ShapesDictRef.slot(Plane)
    tree = nustd.kv.ShapesDictRef.slot(Node)
    kernel = nustd.kv.ShapeRef.slot(Kernel)
    connections = nustd.kv.ShapesDictRef.slot(Connection)
    state = nustd.kv.ShapeRef.slot(SpaceState)
    settings = nustd.kv.ShapeRef.slot(SpaceSettings)
    pinned = nustd.kv.ListRef.slot(str)
