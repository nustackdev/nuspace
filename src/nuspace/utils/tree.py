"""The walks plane ops make over the tree: down one subtree, up from a plane to root.

Both read only the rows they pass. Down follows ``children`` and ``cells``,
which list live rows only (a removal takes the row out of its parent's
list), so a walk from a live plane meets no removed row. Up follows
``parent`` and stops at root, whose parent is ``""``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.errors import Refused
from nuspace.shapes.space import Space

from .checks import refuse


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["no_cycle", "subtree"]


class _Down(nu.Shape):
    """A walk down: the planes still to visit."""

    stack = nu.ListRef.slot(str)


class _Up(nu.Shape):
    """A walk up: the plane it stands on."""

    at = nu.StrRef.slot()


def subtree(
    top: nu.StrArg,
    plane: Callable[[nu.Str], nu.Nu],
    cell: Callable[[nu.Str], nu.Nu],
) -> nu.Nu:
    """``plane(p)`` for ``top`` and every plane below it, ``cell(c)`` for each of their cells.

    Depth first, a stack in a mem frame: each plane is visited once, then its
    cells, then its children are pushed. O(subtree): one read of each
    plane's ``cells`` and ``children``, nothing else. No bracket.
    """
    stack = _Down.stack
    rows = Space.planes

    def visit(p: nu.ObjectRef) -> nu.Nu:
        at = nu.Str(p)
        cells = nu.list(rows[at].cells.keys())
        return (
            plane(at)
            >> nu.ForEachDo(cells, lambda c: cell(nu.Str(c)))
            >> stack.extend(nu.list(rows[at].children.keys()))
        )

    walk = nu.WhileDo(stack.len() > 0, nu.let(stack.pop(), visit))
    return nu.Frame(_Down, walk, stack=nu.List.of(top))


def no_cycle(id: nu.StrArg, parent: nu.StrArg) -> nu.Nu:
    """Refuse hanging ``id`` under ``parent`` when ``parent`` is ``id`` or sits below it.

    Climbs from ``parent`` through ``parent`` slots to root: O(depth),
    whatever hangs below ``id``. No bracket.

    Raises:
        Refused: The move would make a cycle.
    """
    at = _Up.at
    climb = nu.WhileDo((at != "").and_(at != id), at.set(Space.planes[at].parent.fallback("")))
    cycle = refuse(at == id, Refused, "plane ", id, " cannot move under itself or a plane below it")
    return nu.Frame(_Up, climb >> cycle, at=parent)
