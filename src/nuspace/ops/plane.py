"""Plane ops: make one, name it, annotate it, drop it.

Its props (``system``, ``ui``, ``made_by``, ``backend``) are set when it is
made. Its meta is free and merged into any time.

A plane's icon is ``meta.icon``, a string: ``"lucide:<name>"`` for one of the
shell's icon pack, ``"emoji:<char>"`` for an emoji, ``""`` or absent for the
default. :func:`plane_icon` is the one place a spelling is read.

A plane is structure plus the one run setting, its ``backend``: nothing else
here says how anything runs. Which
cells are on it and in what order is :mod:`nuspace.ops.cell`; where it hangs
is :mod:`nuspace.ops.tree`; whether it is pinned is :mod:`nuspace.ops.pin`.
"""

from __future__ import annotations

from typing import Any

import nu
from nuspace.shapes import ROOT, Space

from .kernel import kill, live_runs_of
from .pin import unpin
from .read import plane_exists
from .state import drop_plane_state
from .tree import link, subtree, unlink
from .utils import MintId, atomic, atomic_state, binding, flag, fresh


__all__ = [
    "ICON_EMOJI",
    "ICON_LUCIDE",
    "add_plane",
    "plane_icon",
    "remove_plane",
    "rename_plane",
    "set_plane_icon",
    "set_plane_meta",
]


#: The prefix of an icon from the shell's pack, a lucide name after it.
ICON_LUCIDE = "lucide:"

#: The prefix of an emoji icon, the emoji itself after it.
ICON_EMOJI = "emoji:"

#: What :func:`add_plane` says when it is given no backend.
NO_BACKEND = "A plane needs a backend, eg mp or async: none was given"


def _merge(meta: nu.Nu, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a meta dict: named keys replaced, others kept."""
    return meta.update(fields)


def _refuse_empty(backend: nu.StrArg) -> nu.Nu:
    """Raise :data:`NO_BACKEND` when ``backend`` evaluates to ``""``: the commit makes nothing."""
    if isinstance(backend, str):
        return nu.Noop()
    return nu.IfDo(nu.Eq(backend, nu.Str("")), nu.Raise(nu.Str(NO_BACKEND), exc_cls=ValueError))


def add_plane(
    plane_id: nu.StrArg | None = None,
    *,
    backend: nu.StrArg,
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
        backend: Prop, the backend its runs execute on, by the name it was
            registered under at open (``mp``, ``async``). Required: there is
            no default, and an empty one is refused. Picked by the kind of
            work its cells do: many awaiting tasks run well on ``async``,
            sync code on ``mp``.
        name: What to call it.
        parent: The tree node to hang it under, ``ROOT`` or a plane id. A
            parent that does not exist falls back to ``ROOT``.
        system: Prop, a protected plane, eg a service or home.
            ``remove_plane`` refuses it.
        ui: Prop, the shell draws it and nav brings it up when routed.
        made_by: Prop, the registered Plane it was created from. Nothing
            groups by it.
        meta: Fields to merge into its meta.

    The props are written every time, so an existing plane given again takes
    the ones passed now.

    Yields:
        The plane id.

    Raises:
        ValueError: ``backend`` is empty: at build when it is a ``str``, at
            run time, before the commit writes anything, when it is a term.
    """
    if isinstance(backend, str) and not backend:
        raise ValueError(NO_BACKEND)

    def write(pid_name: str) -> nu.Nu:
        return plane_writes(
            nu.StrRef(pid_name),
            backend=backend,
            name=name,
            parent=parent,
            system=system,
            ui=ui,
            made_by=made_by,
            meta=meta,
        )

    value = MintId("p") if plane_id is None else nu.Str(plane_id)
    return atomic(binding(value, write, tag="p"))


def plane_writes(
    plane_id: nu.StrArg,
    *,
    backend: nu.StrArg,
    name: nu.StrArg = "",
    parent: nu.StrArg = ROOT,
    system: nu.BoolArg = False,
    ui: nu.BoolArg = False,
    made_by: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
) -> nu.Nu:
    """:func:`add_plane`'s writes for a plane id already known. No bracket."""
    row = Space.planes[plane_id]
    under = nu.If(nu.Or(nu.Eq(parent, nu.Str(ROOT)), plane_exists(parent)), parent, nu.Str(ROOT))
    writes = (
        _refuse_empty(backend)
        >> nu.IfDo(nu.Not(plane_exists(plane_id)), row.order.set(nu.Literal([])))
        >> row.name.set(name)
        >> row.props.system.set(system)
        >> row.props.ui.set(ui)
        >> row.props.made_by.set(made_by)
        >> row.props.backend.set(backend)
    )
    if meta is not None:
        writes = writes >> _merge(row.meta, meta)
    return writes >> unlink(plane_id) >> link(plane_id, under)


def remove_plane(plane_id: nu.StrArg) -> nu.Nu:
    """Drop a plane, its cells, and every plane nested below it, unpinning each. Then their state.

    Refused when the plane or any plane below it is a system plane. Live
    runs of every plane going are killed in the same commit, so nothing keeps
    running against rows that are gone.

    Two commits: the rows, which yields the planes that went, then their
    state, one subtree delete per plane (its cells' state inside it). Rows
    first, as :func:`~nuspace.ops.cell.remove_cell` does, so no plane still
    there reads its state gone.

    Yields:
        True when removed, False when refused or missing.
    """
    gone = fresh("removed")
    ids = nu.ObjectRef(gone)
    each = fresh("removed_each")
    drop = atomic_state(nu.ForEachDo(nu.List(ids), drop_plane_state(nu.StrRef(each)), item=each))
    removed = nu.Gt(nu.List(ids).len(), nu.Int(0))
    return nu.Let(gone, _remove_rows(plane_id), binding(removed, lambda _: drop, tag="removed_ok"))


def _remove_rows(plane_id: nu.StrArg) -> nu.Nu:
    """:func:`remove_plane`'s Space commit. Yields the plane ids removed, ``[]`` when refused.

    Yielded rather than set on an attr: an attr set in a retried bracket
    does not reach past it.
    """

    def body(out: str) -> nu.Nu:
        removed = nu.ObjectRef(out)

        def drop(ids: nu.ObjectRef) -> nu.Nu:
            item = fresh("drop")
            at = nu.StrRef(item)
            system = nu.List(
                nu.Collect(
                    nu.Filter(nu.List(ids), flag(Space.planes[at].props.system, False), key=item)
                )
            )
            gone = nu.List(ids)
            each = fresh("drop_each")
            each_ref = nu.StrRef(each)
            delete = nu.ForEachDo(
                gone,
                unlink(each_ref)
                >> unpin(each_ref)
                >> nu.IfDo(Space.planes.contains(each_ref), Space.planes.del_item(each_ref))
                >> nu.IfDo(Space.tree.contains(each_ref), Space.tree.del_item(each_ref)),
                item=each,
            )
            ok = nu.And(plane_exists(plane_id), nu.Eq(system.len(), nu.Int(0)))
            return nu.IfDo(ok, live_runs_of(gone.contains, kill) >> delete >> removed.set(gone))

        return subtree(plane_id, drop)

    return atomic(binding(nu.Literal([]), body, tag="remove"))


def rename_plane(plane_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a plane's name. A no-op when it is missing."""
    return atomic(nu.IfDo(plane_exists(plane_id), Space.planes[plane_id].name.set(name)))


def set_plane_meta(plane_id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a plane's meta, shallow. A no-op when it is missing.

    Props are not reachable from here: they are set by :func:`add_plane`.
    """
    return atomic(nu.IfDo(plane_exists(plane_id), _merge(Space.planes[plane_id].meta, fields)))


def plane_icon(icon: str) -> str:
    """The stored spelling of an icon: ``lucide:<name>``, ``emoji:<char>`` or ``""``.

    A bare name, with no prefix, is a lucide name, which is how a registered
    Plane names its icon. Surrounding space is dropped.

    Raises:
        ValueError: A prefix that is neither ``lucide:`` nor ``emoji:``, or
            one with nothing after it.
    """
    icon = icon.strip()
    if not icon:
        return ""
    if icon.startswith((ICON_LUCIDE, ICON_EMOJI)):
        if not icon.partition(":")[2].strip():
            raise ValueError(f"icon {icon!r} names nothing")
        return icon
    if ":" in icon:
        raise ValueError(f"icon {icon!r} is neither lucide: nor emoji:")
    return ICON_LUCIDE + icon


def set_plane_icon(plane_id: nu.StrArg, icon: nu.StrArg) -> nu.Nu:
    """Set a plane's icon: a merge of ``meta.icon``. A no-op when it is missing.

    Args:
        plane_id: The plane.
        icon: ``"lucide:<name>"``, ``"emoji:<char>"``, a bare lucide name,
            or ``""`` for the default. A Python string is checked and
            spelled by :func:`plane_icon`; a term is stored as it evaluates.
    """
    value = nu.Str(plane_icon(icon)) if isinstance(icon, str) else icon
    return set_plane_meta(plane_id, nu.Dict.of(icon=value))
