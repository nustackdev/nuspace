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
from .utils import atomic


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
    going, edge = nu.List(_Walk.going), nu.List(_Walk.edge)
    below = nu.Flatten(nu.Map(edge, lambda node: nu.list(Space.tree[nu.Str(node)].children)))
    step = nu.List(nu.Collect(nu.Filter(nu.Unique(below), lambda p: going.contains(p).not_())))
    walk = nu.WhileDo(edge.len() > 0, _Walk.going.set(going + edge) >> _Walk.edge.set(step))
    return nu.Frame(_Walk, walk >> body(_Walk.going), going=[], edge=nu.List.of(plane_id))


def unlink(plane_id: nu.StrArg) -> nu.Nu:
    """Drop ``plane_id`` from every tree node listing it. No bracket."""
    return nu.ForEachDo(
        nu.list(Space.tree.keys()),
        lambda node: Space.tree[nu.Str(node)].children.remove(plane_id, missing_ok=True),
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
    make a cycle. Whether it moved is in the record: the plane's parent
    and its place among the children.
    """

    def move(moved: nu.ObjectRef) -> nu.Nu:
        def check(ids: nu.Nu) -> nu.Nu:
            ok = nu.And(
                plane_exists(plane_id),
                (nu.Str(parent) == ROOT).or_(plane_exists(parent)),
                nu.List(ids).contains(parent).not_(),
            )
            return moved.set(ok)

        moving = unlink(plane_id) >> link(plane_id, parent, index)
        return subtree(plane_id, check) >> nu.IfDo(nu.Bool(moved), moving)

    return atomic(nu.let(False, move))
