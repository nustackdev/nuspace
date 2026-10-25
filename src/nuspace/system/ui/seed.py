"""Seeding a system ui plane: made once at open with its cells, the owner's after that.

Home, settings and search are seeded so (:mod:`nuspace.system.ui`). A seeded
plane has a fixed id, its cells fixed ids under it (:func:`seeded_id`).
"""

from __future__ import annotations

import nu
from nuspace.ops.cell import HasUi, cell_writes
from nuspace.ops.pin import pin as pin_last
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import atomic
from nuspace.shapes import Space

from ..kernel.utils import snap


__all__ = ["META", "seed", "seeded_id"]


#: A seeded plane's meta, its icon added.
META = {"editable": True, "full_width": False}


class _Seeding(nu.Shape):
    """What :func:`seed` works out before its bracket: each cell's ``has_ui``, by cell id."""

    ui = nu.DictRef.slot(bool)


def seeded_id(plane: str, name: str) -> str:
    """The id of the cell :func:`seed` makes under this name: the plane's id, then the name.

    Fixed, so the cell is found without a lookup, and under the plane's id,
    so two seeded planes' cells of one name never meet.
    """
    return f"{plane}_{name}"


def seed(
    plane: str,
    name: str,
    icon: str,
    cells: tuple[tuple[str, str], ...],
    *,
    backend: str,
    pin: bool = True,
) -> nu.Nu:
    """A system ui plane and its cells, pinned last, when the plane was never made. Idempotent.

    Missing means ``add_plane`` never wrote it (no name), so a plane the owner
    has edited since, cells removed or renamed included, is left as it is,
    and so is a pin the owner has taken off. One commit: the plane, its
    cells and its pin land together. Each cell's ``has_ui`` is worked out
    first, outside the bracket, and only when the plane is missing.

    Args:
        plane: The plane id, fixed.
        name: What the plane is called.
        icon: Its icon, eg ``"emoji:<char>"``.
        cells: ``(name, source)`` in order. Each cell's id is
            :func:`seeded_id`.
        backend: The backend its runs execute on. Required: there is no default.
        pin: Pin it, after the pins there are.
    """
    missing = Space.planes[plane].contains("name").not_()
    writes = plane_writes(
        plane,
        backend=backend,
        name=name,
        system=True,
        ui=True,
        made_by="",
        meta={**META, "icon": icon},
    )
    ids = [(seeded_id(plane, name), name, source) for name, source in cells]
    for cell, name, source in ids:
        writes = writes >> cell_writes(plane, cell, source, _Seeding.ui[cell], name=name)
    if pin:
        writes = writes >> pin_last(plane)
    uis = [_Seeding.ui[cell].set(HasUi(source, plane, cell)) for cell, _, source in ids]
    body = nu.Sequential(*uis, atomic(nu.IfDo(missing, writes)))
    return nu.IfDo(snap(missing), nu.Frame(_Seeding, body, ui={}))
