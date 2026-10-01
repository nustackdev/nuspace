"""The tree: which plane hangs under which.

Nesting is a relation between planes and lives in ``Space.tree``, so every
plane stays one lookup away in ``Space.planes`` and moving a subtree is two
list edits: unlink from the old node, link under the new one.

A node's ``children`` is also its sibling order: a new plane is appended,
a move puts it where it is asked, a removal drops it and closes the gap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.shapes import ROOT, Space

from .read import plane_exists
from .utils import Then, atomic, fresh


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["move_plane"]


class _Walk(nu.Shape):
    """A tree walk's state: every plane it reached, and the edge it goes down next."""

    going = nu.ObjectRef.slot()
    edge = nu.ObjectRef.slot()


def subtree(plane_id: nu.StrArg, body: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """Walk the tree below ``plane_id``, then run ``body(ids)``.

    ``ids`` holds the plane and every descendant, breadth first. The walk
    reads the store as it goes and carries what it already reached, so a
    cycle written by hand ends rather than going round forever.
    """
    going, edge = _Walk.going, _Walk.edge
    at, reached = fresh("edge_at"), fresh("reached")
    step = nu.List(
        nu.Collect(
            nu.Filter(
                nu.Unique(
                    nu.Flatten(
                        nu.Map(
                            nu.List(edge),
                            nu.list(Space.tree[nu.Str(nu.Attr(at))].children),
                            key=at,
                        )
                    )
                ),
                nu.Not(nu.List(going).contains(nu.Attr(reached))),
                key=reached,
            )
        )
    )
    walk = nu.WhileDo(
        nu.Gt(edge.len(), nu.Int(0)),
        going.set(nu.List(going) + nu.List(edge)) >> edge.set(step),
    )
    return nu.Frame(_Walk, walk >> body(going), going=nu.Literal([]), edge=nu.List.of(plane_id))


def unlink(plane_id: nu.StrArg) -> nu.Nu:
    """Drop ``plane_id`` from every tree node listing it. No bracket."""
    item = fresh("unlink")
    node = Space.tree[nu.Str(nu.Attr(item))].children
    return nu.ForEachDo(
        nu.list(Space.tree.keys()),
        nu.IfDo(node.contains(plane_id), node.remove(plane_id)),
        item=item,
    )


def link(plane_id: nu.StrArg, node_id: nu.StrArg, index: nu.IntArg | None = None) -> nu.Nu:
    """List ``plane_id`` under ``node_id`` at ``index`` (end when None). No bracket."""
    kids = Space.tree[node_id].children
    return kids.append(plane_id) if index is None else kids.insert(index, plane_id)


def move_plane(
    plane_id: nu.StrArg, *, parent: nu.StrArg = ROOT, index: nu.IntArg | None = None
) -> nu.Nu:
    """Hang ``plane_id`` under ``parent`` (a plane id or ``ROOT``) at ``index``.

    Reparents and reorders in one: ``index`` is a position among
    ``parent``'s children once the plane is out of them, the end when None.
    Anything moves, system planes and home too. Refused when either is
    missing, or when ``parent`` is the plane or sits below it: that would
    make a cycle.

    Yields:
        True when moved, False when refused.
    """
    return atomic(nu.let(False, lambda moved: _move_body(plane_id, parent, index, moved)))


def _move_body(
    plane_id: nu.StrArg, parent: nu.StrArg, index: nu.IntArg | None, moved: nu.ObjectRef
) -> nu.Nu:
    """Decide into ``moved``, then move the plane when it said yes, and yield the decision."""

    def check(ids: nu.Nu) -> nu.Nu:
        ok = nu.And(
            plane_exists(plane_id),
            nu.Or(nu.Eq(parent, nu.Str(ROOT)), plane_exists(parent)),
            nu.Not(nu.List(ids).contains(parent)),
        )
        return moved.set(ok)

    move = subtree(plane_id, check) >> nu.IfDo(
        nu.Bool(moved), unlink(plane_id) >> link(plane_id, parent, index)
    )
    return Then(move, moved)
