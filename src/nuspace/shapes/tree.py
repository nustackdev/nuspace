"""Tree: parent to children between planes."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["ROOT", "Node"]


#: The tree id every top level plane hangs off. Not a plane.
ROOT = "root"


class Node(nu.Shape):
    """One tree entry: a plane's (or :data:`ROOT`'s) child plane ids, in order.

    Nesting lives here and not in storage depth, so every plane stays one
    lookup away in ``Space.planes`` and moving a subtree is two list edits.
    """

    children = nustd.kv.ListRef.slot(str)
