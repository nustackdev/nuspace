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
from .utils import atomic, binding, fresh


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["move_plane"]


def subtree(plane_id: nu.StrArg, body: Callable[[nu.ListAttrRef], nu.Nu]) -> nu.Nu:
    """Walk the tree below ``plane_id``, then run ``body(ids)``.

    ``ids`` is bound to the plane and every descendant, breadth first. The
    walk reads the store as it goes and carries what it already reached, so
    a cycle written by hand ends rather than going round forever.
    """
    going, edge, at, reached = fresh("going"), fresh("edge"), fresh("edge_at"), fresh("reached")
    going_ref, edge_ref = nu.ListAttrRef(going), nu.ListAttrRef(edge)
    step = nu.List(
        nu.Collect(
            nu.Filter(
                nu.Unique(
                    nu.Flatten(
                        nu.Map(
                            nu.List(edge_ref),
                            nu.list(Space.tree[nu.StrAttrRef(at)].children),
                            key=at,
                        )
                    )
                ),
                nu.Not(nu.List(going_ref).contains(nu.StrAttrRef(reached))),
                key=reached,
            )
        )
    )
    walk = nu.WhileDo(
        nu.Gt(edge_ref.len(), nu.Int(0)),
        nu.SetCmd(going_ref, nu.List(going_ref) + nu.List(edge_ref)) >> nu.SetCmd(edge_ref, step),
    )
    return nu.Let(
        going,
        nu.Literal([]),
        nu.Let(edge, nu.List.of(plane_id), walk >> body(going_ref)),
    )


def unlink(plane_id: nu.StrArg) -> nu.Nu:
    """Drop ``plane_id`` from every tree node listing it. No bracket."""
    item = fresh("unlink")
    node = Space.tree[nu.StrAttrRef(item)].children
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
    return atomic(binding(nu.Bool(False), lambda out: _move_body(plane_id, parent, index, out)))


def _move_body(plane_id: nu.StrArg, parent: nu.StrArg, index: nu.IntArg | None, out: str) -> nu.Nu:
    """Decide into the attr ``out``, then move the plane when it said yes."""
    flag_ref = nu.BoolAttrRef(out)

    def check(ids: nu.ListAttrRef) -> nu.Nu:
        ok = nu.And(
            plane_exists(plane_id),
            nu.Or(nu.Eq(parent, nu.Str(ROOT)), plane_exists(parent)),
            nu.Not(nu.List(ids).contains(parent)),
        )
        return nu.SetCmd(flag_ref, ok)

    return subtree(plane_id, check) >> nu.IfDo(
        flag_ref, unlink(plane_id) >> link(plane_id, parent, index)
    )
