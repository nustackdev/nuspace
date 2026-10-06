"""Nesting: which plane hangs under which.

Two facts kept together, in one commit, the way a plane's ``cells`` and a
cell's ``plane`` are: the parent lists the plane in its ``children``, the
plane names it in ``parent``. A top level plane has ``""`` for a parent and
``Space.top`` lists it. So every plane stays one lookup away in
``Space.planes``, its parent is one read, and moving a subtree is two list
edits: unlink from the old parent, link under the new one.

A ``children`` list is also its sibling order: a new plane is appended, a
move puts it where it is asked, a removal drops it and closes the gap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.shapes import Space

from .read import plane_exists
from .utils import atomic


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["move_plane"]


def kids(parent: nu.StrArg, write: Callable[[nu.ListRef], nu.Nu]) -> nu.Nu:
    """``write`` over the list of ``parent``'s children, ``Space.top`` for ``""``. No bracket."""
    return nu.IfDo(nu.Str(parent) == "", write(Space.top), write(Space.planes[parent].children))


class _Walk(nu.Shape):
    """A walk down: every plane it reached, and the edge it goes down next."""

    going = nu.ObjectRef.slot()
    edge = nu.ObjectRef.slot()


def subtree(plane_id: nu.StrArg, body: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """Walk the planes below ``plane_id``, then run ``body(ids)``.

    ``ids`` holds the plane and every descendant, breadth first. The walk
    reads the store as it goes and carries what it already reached, so a
    cycle written by hand ends rather than going round forever.
    """
    going, edge = nu.List(_Walk.going), nu.List(_Walk.edge)
    below = nu.Flatten(nu.Map(edge, lambda p: nu.list(Space.planes[nu.Str(p)].children)))
    step = nu.List(nu.Collect(nu.Filter(nu.Unique(below), lambda p: going.contains(p).not_())))
    walk = nu.WhileDo(edge.len() > 0, _Walk.going.set(going + edge) >> _Walk.edge.set(step))
    return nu.Frame(_Walk, walk >> body(_Walk.going), going=[], edge=nu.List.of(plane_id))


class _Climb(nu.Shape):
    """A walk up: the plane it stands on."""

    at = nu.StrRef.slot()


def within(plane_id: nu.StrArg, node: nu.StrArg, body: Callable[[nu.Bool], nu.Nu]) -> nu.Nu:
    """``body(inside)``, ``inside`` whether ``node`` is ``plane_id`` or sits below it.

    Climbs from ``node`` through ``parent``: as many reads as ``node`` is
    deep, whatever hangs below ``plane_id``.
    """
    at = _Climb.at
    climb = nu.WhileDo(
        (at != "").and_(at != plane_id), at.set(Space.planes[at].parent.fallback(""))
    )
    return nu.Frame(_Climb, climb >> body(at == plane_id), at=node)


def unlink(plane_id: nu.StrArg) -> nu.Nu:
    """Take ``plane_id`` out of its parent's children. No bracket.

    Touches the one list its ``parent`` names. A plane never linked has no
    ``parent`` and nothing to take it out of.
    """
    parent = Space.planes[plane_id].parent
    out = kids(parent.fallback(""), lambda listed: listed.remove(plane_id, missing_ok=True))
    return nu.IfDo(parent.exists(), out)


def link(plane_id: nu.StrArg, parent: nu.StrArg, index: nu.IntArg | None = None) -> nu.Nu:
    """List ``plane_id`` under ``parent`` (``""``, the top) at ``index``, the end when None.

    No bracket.
    """

    def put(listed: nu.ListRef) -> nu.Nu:
        return listed.append(plane_id) if index is None else listed.insert(index, plane_id)

    return kids(parent, put) >> Space.planes[plane_id].parent.set(parent)


def move_plane(
    plane_id: nu.StrArg, *, parent: nu.StrArg = "", index: nu.IntArg | None = None
) -> nu.Nu:
    """Hang ``plane_id`` under ``parent`` (a plane id, ``""`` for the top) at ``index``.

    Reparents and reorders in one: ``index`` is a position among
    ``parent``'s children once the plane is out of them, the end when None.
    Anything moves, system planes and home too. Refused when either is
    missing, or when ``parent`` is the plane or sits below it: that would
    make a cycle. Whether it moved is in the record: the plane's parent
    and its place among the children.
    """

    def check(inside: nu.Bool) -> nu.Nu:
        there = (nu.Str(parent) == "").or_(plane_exists(parent))
        ok = nu.And(plane_exists(plane_id), there, inside.not_())
        return nu.IfDo(ok, unlink(plane_id) >> link(plane_id, parent, index))

    return atomic(within(plane_id, parent, check))
