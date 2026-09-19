"""What a person does to one Plane: make it, name it, say how it runs, drop it.

A Plane is arrangement, so everything here is about how the Plane meets the
world and nothing here is about a program. Which Cells are on it, and in what
order, is :mod:`nuspace.ops.cell`, which is the only writer of either.

Dropping a Plane is the one op here that reaches past the Plane it was given:
``cascade_delete`` says which Planes go when this one goes, both sides of a
mutual relation declare it, and a walk that reads it has to carry the ids it
already reached or a pair takes itself round forever.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.ops.utils import atomic, flag, mint_ordered_id, text
from nuspace.shapes import (
    DEFAULT_EDITABLE,
    DEFAULT_EXEC_MODE,
    DEFAULT_GROUP,
    DEFAULT_TRIGGER,
    DEFAULT_UI,
    Space,
)


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "add_plane",
    "plane_cascade",
    "plane_editable",
    "plane_exec_mode",
    "plane_group",
    "plane_name",
    "plane_props",
    "plane_trigger",
    "plane_ui",
    "plane_writes",
    "remove_plane",
    "rename_plane",
    "set_plane_group",
    "set_plane_props",
]


#: What the delete walk keeps between turns, and what its two readers bind
#: the id they are looking at under. Parallel arms share one ``ctx.attrs``,
#: so every one of these is namespaced to this module and kept apart from the
#: others.
_GOING = "_np_going"
_EDGE = "_np_edge"
_EDGE_AT = "_np_edge_at"
_REACHED_AT = "_np_reached_at"
_DROP_AT = "_np_drop_at"

_going = nu.ListAttrRef(_GOING)
_edge = nu.ListAttrRef(_EDGE)
_edge_at = nu.StrAttrRef(_EDGE_AT)
_reached_at = nu.StrAttrRef(_REACHED_AT)
_drop_at = nu.StrAttrRef(_DROP_AT)


# --- write -----------------------------------------------------------------


def plane_writes(
    *,
    plane_id: nu.StrArg,
    name: nu.StrArg | None = None,
    group: nu.StrArg = DEFAULT_GROUP,
    exec_mode: nu.StrArg = DEFAULT_EXEC_MODE,
    trigger: nu.StrArg = DEFAULT_TRIGGER,
    ui: nu.BoolArg = DEFAULT_UI,
    editable: nu.BoolArg = DEFAULT_EDITABLE,
    cascade_delete: Sequence[nu.StrArg] | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Everything a whole Plane is, as writes, with no bracket of its own.

    :func:`add_plane` is this in a commit and is what a caller making one
    Plane wants. This one is for the caller making several that have to land
    together: a Transaction inside a Transaction opens a second one and
    commits it on its own, so composing the ops would be one commit each and
    a pair would be observable half made.

    Args:
        plane_id: the Plane's key.
        name: what to call it. The id when absent.
        group: which family a ``+`` built it out of.
        exec_mode: ``async`` puts the whole Plane in one process, ``mp``
            gives each Cell a process of its own.
        trigger: when the Plane is up: ``boot``, ``manual`` or ``nav``.
        ui: whether the Plane draws at all.
        editable: whether a person can author its Cells from the Viewer.
        cascade_delete: the Planes that go when this one goes. Left unwritten
            when absent or empty, because an unwritten list already reads as
            no Planes and a row saying so says nothing.
        root: the Space shape class.
    """
    plane = root.planes[plane_id]
    written = (
        plane.name.set(plane_id if name is None else name)
        >> plane.group.set(group)
        >> plane.props.exec_mode.set(exec_mode)
        >> plane.props.trigger.set(trigger)
        >> plane.props.ui.set(ui)
        >> plane.props.editable.set(editable)
    )
    if not cascade_delete:
        return written
    return written >> plane.cascade_delete.set(nu.List.of(*cascade_delete))


def add_plane(
    *,
    plane_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    group: nu.StrArg = DEFAULT_GROUP,
    exec_mode: nu.StrArg = DEFAULT_EXEC_MODE,
    trigger: nu.StrArg = DEFAULT_TRIGGER,
    ui: nu.BoolArg = DEFAULT_UI,
    editable: nu.BoolArg = DEFAULT_EDITABLE,
    cascade_delete: Sequence[nu.StrArg] | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Write a whole Plane: its name, its group and its four props, in one commit.

    A Plane arrives complete or not at all, so the runtime reading this row
    never has to decide what a half written Plane means. Its two containers
    need no creating: a container ref always materialises a view, so a Plane
    with nothing on it reads as a Plane with no Cells.

    Args:
        plane_id: the Plane's key. Minted in creation order when absent, in
            which case the caller never learns it, so pass
            ``mint_ordered_id("p")`` yourself to address the Plane after.
        name: what to call it. The id when absent.
        group: which family a ``+`` built it out of.
        exec_mode: ``async`` puts the whole Plane in one process, ``mp``
            gives each Cell a process of its own.
        trigger: when the Plane is up: ``boot``, ``manual`` or ``nav``.
        ui: whether the Plane draws at all.
        editable: whether a person can author its Cells from the Viewer.
        cascade_delete: the Planes that go when this one goes.
        root: the Space shape class.
    """
    # Minted while the tree is built rather than while it runs, so running one
    # tree twice rewrites one Plane instead of adding a second.
    plane_id = mint_ordered_id("p") if plane_id is None else plane_id
    return atomic(
        plane_writes(
            plane_id=plane_id,
            name=name,
            group=group,
            exec_mode=exec_mode,
            trigger=trigger,
            ui=ui,
            editable=editable,
            cascade_delete=cascade_delete,
            root=root,
        ),
        root,
    )


def _reached(root: type[Space]) -> nu.Nu:
    """Every Plane the ids on the edge name, minus the ones already going.

    One turn of the walk outward. Subtracting what is already going is both
    halves of the visited set: it is what ends a mutual pair, and it is what
    keeps an id out of two edges, which is why the loop cannot outlive the
    Planes in the Space.
    """
    return nu.List(
        nu.Collect(
            nu.Filter(
                nu.Unique(
                    nu.Flatten(
                        nu.Map(
                            nu.List(_edge),
                            # Total: an unwritten list reads as no Planes, and
                            # so does one on a row nobody ever made, so a
                            # dangling id costs a turn and nothing else.
                            nu.list(root.planes[_edge_at].cascade_delete),
                            key=_EDGE_AT,
                        )
                    )
                ),
                nu.Not(nu.List(_going).contains(_reached_at)),
                key=_REACHED_AT,
            )
        )
    )


def remove_plane(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Drop a Plane, every Cell on it, and every Plane it says goes with it.

    A Plane's Cells live under the Plane, so the row carries them out with it
    and there is nothing to walk there. What is walked is ``cascade_delete``:
    it holds plane ids, both sides of a mutual relation declare it, and a job
    and the Plane that draws it name each other, so a walk that did not carry
    what it had already reached would go round the pair forever.

    The walk is breadth first and reads the store as it goes. ``going`` is
    every id that will be dropped and is also the visited set; ``edge`` is
    the ids whose own lists have not been read yet. A turn moves the edge
    into ``going`` and replaces it with whatever that edge named and ``going``
    does not already hold, so no id is ever on two edges and the loop ends
    after at most one turn per Plane in the Space.

    Dropping comes after the walk rather than during it, so nothing the walk
    still has to read is gone by the time it gets there. Each drop is guarded
    rather than bare: ``del_item`` on a missing key raises, an id in a cascade
    list is not promised to name a Plane, and removing something already gone
    is what a retried click does.
    """
    planes = root.planes
    return atomic(
        nu.SetCmd(_going, nu.List.of())
        >> nu.SetCmd(_edge, nu.List.of(plane_id))
        >> nu.WhileDo(
            nu.Gt(_edge.len(), nu.Int(0)),
            nu.SetCmd(_going, nu.List(_going) + nu.List(_edge)) >> nu.SetCmd(_edge, _reached(root)),
        )
        >> nu.ForEachDo(
            nu.List(_going),
            nu.IfDo(planes.contains(_drop_at), planes.del_item(_drop_at)),
            item=_DROP_AT,
        ),
        root,
    )


def rename_plane(plane_id: nu.StrArg, name: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Replace a Plane's name.

    ``name`` sits outside ``props``, so renaming is not a change to how the
    Plane runs and nothing restarts.
    """
    planes = root.planes
    return atomic(nu.IfDo(planes.contains(plane_id), planes[plane_id].name.set(name)), root)


def set_plane_group(plane_id: nu.StrArg, group: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Move a Plane into another family.

    ``group`` sits outside ``props`` alongside ``name``, so this moves which
    section of the sidebar the Plane is listed in and nothing restarts. What
    the Plane holds is whatever the group it was born into put there: a group
    decides what a ``+`` makes and never what a Plane that exists does.
    """
    planes = root.planes
    return atomic(nu.IfDo(planes.contains(plane_id), planes[plane_id].group.set(group)), root)


def set_plane_props(
    plane_id: nu.StrArg,
    *,
    exec_mode: nu.StrArg | None = None,
    trigger: nu.StrArg | None = None,
    ui: nu.BoolArg | None = None,
    editable: nu.BoolArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Change how a Plane runs or how it is drawn. Only what is named is written.

    One commit, so the runtime watching this node never reads a Plane half
    rearranged: it wakes once and sees every prop that moved.
    """
    props = root.planes[plane_id].props
    writes = [
        ref.set(value)
        for ref, value in (
            (props.exec_mode, exec_mode),
            (props.trigger, trigger),
            (props.ui, ui),
            (props.editable, editable),
        )
        if value is not None
    ]
    if not writes:
        return nu.Noop()
    return atomic(nu.IfDo(root.planes.contains(plane_id), nu.Sequential(*writes)), root)


# --- read ------------------------------------------------------------------


def plane_name(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Plane's name, its id where nobody gave it one."""
    return text(root.planes[plane_id].name, plane_id)


def plane_group(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Which family a Plane was born into. The default where nothing was written.

    A Plane written before groups existed reads as a page, which is what one
    is: somewhere a person writes and reads.
    """
    return text(root.planes[plane_id].group, DEFAULT_GROUP)


def plane_cascade(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """The Planes that go when this one goes, as a list of ids.

    Empty where nothing was written, and the ids are not promised to name
    Planes: what a relation pointed at can be dropped on its own.
    """
    return nu.list(root.planes[plane_id].cascade_delete)


def plane_exec_mode(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Where a Plane's Cells run. The default where nothing was written."""
    return text(root.planes[plane_id].props.exec_mode, DEFAULT_EXEC_MODE)


def plane_trigger(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """When a Plane is up. The default where nothing was written."""
    return text(root.planes[plane_id].props.trigger, DEFAULT_TRIGGER)


def plane_ui(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether a Plane draws. The default where nothing was written."""
    return flag(root.planes[plane_id].props.ui, DEFAULT_UI)


def plane_editable(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether a person can author a Plane's Cells from the Viewer."""
    return flag(root.planes[plane_id].props.editable, DEFAULT_EDITABLE)


def plane_props(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A Plane's four props as one dict.

    Total, so a row somebody wrote by hand reads the same as one this module
    wrote.
    """
    return nu.Dict.of(
        exec_mode=plane_exec_mode(plane_id, root=root),
        trigger=plane_trigger(plane_id, root=root),
        ui=plane_ui(plane_id, root=root),
        editable=plane_editable(plane_id, root=root),
    )
