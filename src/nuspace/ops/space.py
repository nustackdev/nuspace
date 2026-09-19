"""What a person does to a Space: the container of Planes it is.

A Space has no fields of its own. It is the world, so what you do to one is
empty it or ask what is in it, and everything narrower takes the id of a
Plane and lives in :mod:`nuspace.ops.plane`. Making a Space is opening one:
:func:`nuspace.space.open_space` takes the directory's write lock and the
directory is the Space.

There is no cold boot. A container ref always materialises a view, so a
Space nobody has written to reads as a Space with no Planes, and a
subscription over it fires from the first write on. Verified against the
memory stack, a RocksDB store and a pool worker reading through a proxied
Navigator.
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import atomic, flag, text
from nuspace.shapes import (
    DEFAULT_EDITABLE,
    DEFAULT_EXEC_MODE,
    DEFAULT_GROUP,
    DEFAULT_TRIGGER,
    DEFAULT_UI,
    Space,
)


__all__ = [
    "clear_space",
    "plane_exists",
    "plane_ids",
    "plane_rows",
]


#: The name the row readers bind the current Plane under. Parallel arms share
#: one ``ctx.attrs``, so it is namespaced to this module.
_ITEM = "_ns_plane"
_item = nu.AnyAttrRef(_ITEM)


# --- write -----------------------------------------------------------------


def clear_space(*, root: type[Space] = Space) -> nu.Nu:
    """Drop every Plane, leaving the Space open and empty.

    The runtime hears every key go and stops everything that was running.
    The store itself is a directory a process holds a lock on, so this is as
    far as deleting a Space goes from inside a tree.
    """
    return atomic(root.planes.clear(), root)


# --- read ------------------------------------------------------------------


def plane_ids(*, root: type[Space] = Space) -> nu.Nu:
    """Every Plane id in the Space, as a list.

    Ids sort by the moment they were minted, so this is creation order.
    """
    # nu.list, not the bare keys view: the view is lazy, its bracket closes
    # around it, and an undrained one dies later with StorageClosedError.
    return nu.list(root.planes.keys())


def plane_exists(plane_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether the Space holds a Plane under this id.

    ``contains``, because a container ref always materialises a view and so
    ``exists()`` on a row answers True whether or not the row is there.
    """
    return root.planes.contains(plane_id)


def plane_rows(*, root: type[Space] = Space) -> nu.Nu:
    """Every Plane as ``id, name, group, exec_mode, trigger, ui, editable``, one dict each.

    One read fills a sidebar: ``ui`` says whether a Plane is listed at all
    and ``group`` says which section it is listed under. Without it a caller
    reads the ids and then loops in its own language, which puts a python or
    a javascript for loop back in the middle of what is meant to be one tree.
    """
    plane = root.planes[_item]
    return nu.Collect(
        nu.Map(
            plane_ids(root=root),
            nu.Dict.of(
                id=_item,
                name=text(plane.name, _item),
                group=text(plane.group, DEFAULT_GROUP),
                exec_mode=text(plane.props.exec_mode, DEFAULT_EXEC_MODE),
                trigger=text(plane.props.trigger, DEFAULT_TRIGGER),
                ui=flag(plane.props.ui, DEFAULT_UI),
                editable=flag(plane.props.editable, DEFAULT_EDITABLE),
            ),
            key=_ITEM,
        )
    )
