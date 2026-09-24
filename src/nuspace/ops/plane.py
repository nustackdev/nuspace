"""Plane ops: make one, name it, annotate it, drop it.

Its props (``system``, ``ui``, ``made_by``) are set when it is made. Its meta
is free and merged into any time.

A plane is structure only, so nothing here says how anything runs. Which
cells are on it and in what order is :mod:`nuspace.ops.cell`; where it hangs
is :mod:`nuspace.ops.tree`.
"""

from __future__ import annotations

from typing import Any

import nu
from nuspace.shapes import ROOT, Space

from .kernel import stop_runs
from .read import plane_exists
from .tree import link, subtree, unlink
from .utils import MintId, atomic, binding, flag, fresh


__all__ = ["add_plane", "remove_plane", "rename_plane", "set_plane_meta"]


def _merge(meta: nu.Nu, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a meta dict: named keys replaced, others kept."""
    return meta.update(fields)


def add_plane(
    plane_id: nu.StrArg | None = None,
    *,
    name: nu.StrArg = "",
    parent: nu.StrArg = ROOT,
    system: nu.BoolArg = False,
    ui: nu.BoolArg = False,
    made_by: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
) -> nu.Nu:
    """Make a plane with no cells and hang it under ``parent``, in one commit.

    Args:
        plane_id: Its id. Minted when the term is evaluated when absent. An
            existing plane given again keeps its cells and is rewritten and
            moved.
        name: What to call it.
        parent: The tree node to hang it under, ``ROOT`` or a plane id. A
            parent that does not exist falls back to ``ROOT``.
        system: Prop, a protected plane, eg a service or home.
            ``remove_plane`` refuses it.
        ui: Prop, the shell draws it and nav brings it up when routed.
        made_by: Prop, the app that made it, the sidebar section it is
            listed under.
        meta: Fields to merge into its meta.

    The props are written every time, so an existing plane given again takes
    the ones passed now.

    Yields:
        The plane id.
    """

    def write(pid_name: str) -> nu.Nu:
        pid = nu.StrAttrRef(pid_name)
        row = Space.planes[pid]
        under = nu.If(
            nu.Or(nu.Eq(parent, nu.Str(ROOT)), plane_exists(parent)), parent, nu.Str(ROOT)
        )
        writes = (
            nu.IfDo(nu.Not(plane_exists(pid)), row.order.set(nu.Literal([])))
            >> row.name.set(name)
            >> row.props.system.set(system)
            >> row.props.ui.set(ui)
            >> row.props.made_by.set(made_by)
        )
        if meta is not None:
            writes = writes >> _merge(row.meta, meta)
        return writes >> unlink(pid) >> link(pid, under)

    value = MintId("p") if plane_id is None else nu.Str(plane_id)
    return atomic(binding(value, write, tag="p"))


def remove_plane(plane_id: nu.StrArg) -> nu.Nu:
    """Drop a plane, its cells, and every plane nested below it.

    Refused when the plane or any plane below it is a system plane. Live
    runs of every plane going are asked to stop first, so nothing keeps
    running against rows that are gone.

    Yields:
        True when removed, False when refused or missing.
    """

    def body(out: str) -> nu.Nu:
        ok = nu.BoolAttrRef(out)

        def drop(ids: nu.ListAttrRef) -> nu.Nu:
            item = fresh("drop")
            at = nu.StrAttrRef(item)
            system = nu.List(
                nu.Collect(
                    nu.Filter(nu.List(ids), flag(Space.planes[at].props.system, False), key=item)
                )
            )
            gone = nu.List(ids)
            each = fresh("drop_each")
            each_ref = nu.StrAttrRef(each)
            delete = nu.ForEachDo(
                gone,
                unlink(each_ref)
                >> nu.IfDo(Space.planes.contains(each_ref), Space.planes.del_item(each_ref))
                >> nu.IfDo(Space.tree.contains(each_ref), Space.tree.del_item(each_ref)),
                item=each,
            )
            return nu.SetCmd(
                ok, nu.And(plane_exists(plane_id), nu.Eq(system.len(), nu.Int(0)))
            ) >> nu.IfDo(ok, stop_runs(lambda run: gone.contains(run.plane)) >> delete)

        return subtree(plane_id, drop)

    return atomic(binding(nu.Bool(False), body, tag="remove"))


def rename_plane(plane_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a plane's name. A no-op when it is missing."""
    return atomic(nu.IfDo(plane_exists(plane_id), Space.planes[plane_id].name.set(name)))


def set_plane_meta(plane_id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a plane's meta, shallow. A no-op when it is missing.

    Props are not reachable from here: they are set by :func:`add_plane`.
    """
    return atomic(nu.IfDo(plane_exists(plane_id), _merge(Space.planes[plane_id].meta, fields)))
