"""Space: the world. What you open."""

from __future__ import annotations

import nu
import nustd.kv

from .connection import Connection
from .kernel import Kernel
from .plane import Plane
from .tree import Node


__all__ = ["Space"]


class Space(nu.Shape):
    """Planes, the tree between them, the kernel's records, device state.

    ``planes`` is flat, so a plane is one lookup away and a route addresses it
    directly. Nesting is ``tree``, keyed by plane id plus
    :data:`~nuspace.shapes.tree.ROOT`.

    One writer per subtree: people, apps and services write ``planes`` and
    ``tree`` through ops, the kernel writes ``kernel``, the web device writes
    ``connections``.

    ``Space`` is also the store's tag. kv refs find their navigator by root
    shape class, so the store is bound under this class and anything rerooted
    under it resolves there.
    """

    planes = nustd.kv.ShapesDictRef.slot(Plane)
    tree = nustd.kv.ShapesDictRef.slot(Node)
    kernel = nustd.kv.ShapeRef.slot(Kernel)
    connections = nustd.kv.ShapesDictRef.slot(Connection)
