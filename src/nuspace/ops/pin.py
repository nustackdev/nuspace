"""Pins: the planes pinned to the top of the sidebar, in order.

``Space.pinned`` is the one place a pin lives, a list of plane ids. A pin is
a shortcut: the plane stays where it is in the tree. Only a plane the shell
draws (``props.ui``) is pinned; removing a plane unpins it and every plane
below it (:func:`~nuspace.ops.plane.remove_plane`).

An ``index`` is a position in the list with the plane taken out of it. One
out of range, negative included, is the end.
"""

from __future__ import annotations

import nu
from nuspace.shapes import Space

from .read import plane_exists
from .utils import atomic, flag


__all__ = ["move_pin", "pin_plane", "pinned", "unpin_plane"]


def pinned() -> nu.Nu:
    """The pinned plane ids, in order. ``[]`` when nothing was ever pinned. Bare read."""
    return nu.list(Space.pinned)


def unpin(plane_id: nu.StrArg) -> nu.Nu:
    """Drop ``plane_id`` from the pins when it is there. No bracket."""
    pins = Space.pinned
    return nu.IfDo(pins.contains(plane_id), pins.remove(plane_id))


def _place(plane_id: nu.StrArg, index: nu.IntArg) -> nu.Nu:
    """Take ``plane_id`` out of the pins, then put it at ``index``. No bracket."""
    pins = Space.pinned
    at = nu.If(nu.And(nu.Ge(index, nu.Int(0)), nu.Lt(index, pins.len())), index, pins.len())
    return unpin(plane_id) >> pins.insert(at, plane_id)


def pin_plane(plane_id: nu.StrArg, index: nu.IntArg | None = None) -> nu.Nu:
    """Pin a plane at ``index``, the end when None. One commit.

    Already pinned, it stays where it is when ``index`` is None and moves
    there otherwise. A no-op for a plane that is missing or not drawn.
    """
    pins = Space.pinned
    ok = nu.And(plane_exists(plane_id), flag(Space.planes[plane_id].props.ui, False))
    if index is None:
        return atomic(nu.IfDo(nu.And(ok, nu.Not(pins.contains(plane_id))), pins.append(plane_id)))
    return atomic(nu.IfDo(ok, _place(plane_id, index)))


def unpin_plane(plane_id: nu.StrArg) -> nu.Nu:
    """Unpin a plane. The plane itself is left alone. A no-op when it is not pinned."""
    return atomic(unpin(plane_id))


def move_pin(plane_id: nu.StrArg, index: nu.IntArg) -> nu.Nu:
    """Move a pinned plane to ``index``. A no-op when it is not pinned."""
    return atomic(nu.IfDo(Space.pinned.contains(plane_id), _place(plane_id, index)))
