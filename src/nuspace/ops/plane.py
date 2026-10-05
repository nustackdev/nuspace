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
from .state import drop_cell_state, drop_plane_state
from .tree import link, subtree, unlink
from .utils import MintId, atomic, atomic_state


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


def _refuse_empty(backend: nu.StrArg) -> nu.Nu:
    """Raise :data:`NO_BACKEND` when ``backend`` evaluates to ``""``: the commit makes nothing."""
    if isinstance(backend, str):
        return nu.Noop()
    return nu.IfDo(nu.Str(backend) == "", nu.Raise(NO_BACKEND, exc_cls=ValueError))


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
    into: nu.Ref | None = None,
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
        into: Set to the plane id in the commit, for a caller that needs a
            minted one: the record does not say which plane this call made.

    The props are written every time, so an existing plane given again takes
    the ones passed now.

    Raises:
        ValueError: ``backend`` is empty: at build when it is a ``str``, at
            run time, before the commit writes anything, when it is a term.
    """
    if isinstance(backend, str) and not backend:
        raise ValueError(NO_BACKEND)

    def write(pid: nu.ObjectRef) -> nu.Nu:
        writes = plane_writes(
            nu.Str(pid),
            backend=backend,
            name=name,
            parent=parent,
            system=system,
            ui=ui,
            made_by=made_by,
            meta=meta,
        )
        return writes if into is None else writes >> into.set(nu.Str(pid))

    return atomic(nu.let(MintId("p") if plane_id is None else plane_id, write))


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
    writes = (
        _refuse_empty(backend)
        >> nu.IfDo(plane_exists(plane_id).not_(), row.cells.set([]))
        >> row.name.set(name)
        >> row.props.system.set(system)
        >> row.props.ui.set(ui)
        >> row.props.made_by.set(made_by)
        >> row.props.backend.set(backend)
    )
    if meta is not None:
        writes = writes >> row.meta.update(meta)
    under = nu.If((nu.Str(parent) == ROOT).or_(plane_exists(parent)), parent, ROOT)
    return writes >> unlink(plane_id) >> link(plane_id, under)


def remove_plane(plane_id: nu.StrArg) -> nu.Nu:
    """Drop a plane, its cells, and every plane nested below it, unpinning each. Then their state.

    Refused when the plane or any plane below it is a system plane. Live
    runs of every plane going are killed in the same commit, so nothing keeps
    running against rows that are gone. Whether it went is in the record:
    :func:`~nuspace.ops.read.plane_exists`.

    Two commits: the rows, then their state, one subtree delete per plane
    and per cell. The first writes which planes and cells went into slots
    of the op's own, where the second reads them. Rows first, as
    :func:`~nuspace.ops.cell.remove_cell` does, so no plane or cell still
    there reads its state gone.
    """

    def dropped(gone: nu.Ref, cells: nu.Ref) -> nu.Nu:
        planes = nu.ForEachDo(nu.List(gone), lambda p: drop_plane_state(nu.Str(p)))
        return planes >> nu.ForEachDo(nu.List(cells), lambda c: drop_cell_state(nu.Str(c)))

    return nu.let(
        [],
        lambda gone: nu.let(
            [],
            lambda cells: _remove_rows(plane_id, gone, cells) >> atomic_state(dropped(gone, cells)),
        ),
    )


def _remove_rows(plane_id: nu.StrArg, gone: nu.Ref, cells: nu.Ref) -> nu.Nu:
    """:func:`remove_plane`'s Space commit. ``gone`` and ``cells`` set to the ids removed.

    Both ``[]`` when refused. Every try sets them, so after a retried commit
    they hold what the try that landed removed.
    """

    def delete(at: nu.Attr) -> nu.Nu:
        p = nu.Str(at)
        return (
            unlink(p)
            >> unpin(p)
            >> nu.IfDo(Space.planes.contains(p), Space.planes.del_item(p))
            >> nu.IfDo(Space.tree.contains(p), Space.tree.del_item(p))
        )

    def drop(ids: nu.Nu) -> nu.Nu:
        going = nu.List(ids)
        system = going.iter().filter(lambda p: Space.planes[nu.Str(p)].props.system.fallback(False))
        owned = nu.Flatten(nu.Map(going, lambda p: nu.list(Space.planes[nu.Str(p)].cells)))
        removed = (
            live_runs_of(going.contains, kill)
            >> cells.set(nu.List(nu.Collect(owned)))
            >> nu.ForEachDo(nu.List(cells), lambda c: Space.cells.del_item(nu.Str(c)))
            >> nu.ForEachDo(going, delete)
            >> gone.set(going)
        )
        return nu.IfDo(
            plane_exists(plane_id).and_(system.to_list().len() == 0),
            removed,
            gone.set([]) >> cells.set([]),
        )

    return atomic(subtree(plane_id, drop))


def rename_plane(plane_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a plane's name. A no-op when it is missing."""
    return atomic(nu.IfDo(plane_exists(plane_id), Space.planes[plane_id].name.set(name)))


def set_plane_meta(plane_id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a plane's meta, shallow. A no-op when it is missing.

    Props are not reachable from here: they are set by :func:`add_plane`.
    """
    return atomic(nu.IfDo(plane_exists(plane_id), Space.planes[plane_id].meta.update(fields)))


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
