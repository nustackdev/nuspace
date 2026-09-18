"""What a person does to one Plane: make it, name it, say how it runs, drop it.

A Plane is arrangement, so everything here is about how the Plane meets the
world and nothing here is about a program. Which Cells are on it, and in what
order, is :mod:`nuspace.ops.cell`, which is the only writer of either.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import atomic, flag, mint_ordered_id, text
from nuspace.shapes import (
    DEFAULT_EDITABLE,
    DEFAULT_EXEC_MODE,
    DEFAULT_TRIGGER,
    DEFAULT_UI,
    Space,
)


__all__ = [
    "add_plane",
    "plane_editable",
    "plane_exec_mode",
    "plane_name",
    "plane_props",
    "plane_trigger",
    "plane_ui",
    "remove_plane",
    "rename_plane",
    "set_plane_props",
]


# --- write -----------------------------------------------------------------


def add_plane(
    *,
    plane_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    exec_mode: nu.StrArg = DEFAULT_EXEC_MODE,
    trigger: nu.StrArg = DEFAULT_TRIGGER,
    ui: nu.BoolArg = DEFAULT_UI,
    editable: nu.BoolArg = DEFAULT_EDITABLE,
    root: type[Space] = Space,
) -> nu.Nu:
    """Write a whole Plane: its name and its four props, in one commit.

    A Plane arrives complete or not at all, so the runtime reading this row
    never has to decide what a half written Plane means. Its two containers
    need no creating: a container ref always materialises a view, so a Plane
    with nothing on it reads as a Plane with no Cells.

    Args:
        plane_id: the Plane's key. Minted in creation order when absent, in
            which case the caller never learns it, so pass
            ``mint_ordered_id("p")`` yourself to address the Plane after.
        name: what to call it. The id when absent.
        exec_mode: ``async`` puts the whole Plane in one process, ``mp``
            gives each Cell a process of its own.
        trigger: when the Plane is up: ``boot``, ``manual`` or ``nav``.
        ui: whether the Plane draws at all.
        editable: whether a person can author its Cells from the Viewer.
        root: the Space shape class.
    """
    # Minted while the tree is built rather than while it runs, so running one
    # tree twice rewrites one Plane instead of adding a second.
    plane_id = mint_ordered_id("p") if plane_id is None else plane_id
    plane = root.planes[plane_id]
    return atomic(
        plane.name.set(plane_id if name is None else name)
        >> plane.props.exec_mode.set(exec_mode)
        >> plane.props.trigger.set(trigger)
        >> plane.props.ui.set(ui)
        >> plane.props.editable.set(editable),
        root,
    )


def remove_plane(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Drop a Plane and every Cell on it. A no-op when it is not there.

    A Plane's Cells live under the Plane, so the row carries them out with it
    and there is nothing to walk. The runtime hears the key go and stops
    whatever it had running.

    Guarded rather than bare: ``del_item`` on a missing key raises, and
    removing something already gone is what a retried click does.
    """
    planes = root.planes
    return atomic(nu.IfDo(planes.contains(plane_id), planes.del_item(plane_id)), root)


def rename_plane(plane_id: nu.StrArg, name: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Replace a Plane's name.

    ``name`` sits outside ``props``, so renaming is not a change to how the
    Plane runs and nothing restarts.
    """
    planes = root.planes
    return atomic(nu.IfDo(planes.contains(plane_id), planes[plane_id].name.set(name)), root)


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
