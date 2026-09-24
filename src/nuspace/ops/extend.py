"""Extension ops: create a registered Plane, insert a snippet.

Planes and snippets are registry entries, registered by the host at open.
Core ships none privileged: a third party registers the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import nu
from nuspace.shapes import ROOT

from .cell import add_cell
from .plane import add_plane
from .utils import binding


__all__ = ["Plane", "Snippet", "create_plane", "insert_snippet"]


@dataclass(frozen=True)
class Plane:
    """A plane ``+`` can create: data, seeded as is. No build hook.

    Everything it does lives in its cells: args, forms, lists, background
    work. Creating one only seeds it.

    Args:
        name: Registry key, and what the planes created from it record as
            ``made_by``.
        label: What the picker shows, and a new plane's default name.
        icon: A lucide icon name, ``""`` for the default.
        description: One line for the picker.
        meta: What a new plane's meta starts as.
        cells: ``(name, source)`` per cell, in order.
        children: Planes seeded under it, the same shape, in order.
    """

    name: str
    label: str
    icon: str = ""
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    cells: tuple[tuple[str, str], ...] = ()
    children: tuple[Plane, ...] = ()


@dataclass(frozen=True)
class Snippet:
    """Source for one cell, offered from the ``/`` menu.

    Args:
        name: Registry key, and the new cell's name.
        label: What the menu shows.
        source: The cell's prog.
    """

    name: str
    label: str
    source: str


def create_plane(
    spec: Plane,
    *,
    parent: nu.StrArg = ROOT,
    name: nu.StrArg | None = None,
    plane_id: nu.StrArg | None = None,
) -> nu.Nu:
    """Create a plane from ``spec``: drawn, its cells in order, its children under it.

    Several commits, one per plane and cell, like any composite op: a
    reader may see the plane before its cells.

    Args:
        spec: The registered Plane.
        parent: The tree node to hang it under, ``ROOT`` or a plane id.
        name: What to call it. ``spec.label`` when absent.
        plane_id: Its id. Minted when absent. Children always mint theirs.

    Yields:
        The new plane's id.
    """

    def fill(pid_name: str) -> nu.Nu:
        pid = nu.StrAttrRef(pid_name)
        seeds = [add_cell(pid, source, name=cell) for cell, source in spec.cells]
        seeds += [create_plane(child, parent=pid) for child in spec.children]
        return nu.Sequential(*seeds) if seeds else nu.Noop()

    made = add_plane(
        plane_id,
        name=spec.label if name is None else name,
        parent=parent,
        ui=True,
        made_by=spec.name,
        meta=dict(spec.meta),
    )
    return binding(made, fill, tag="create")


def insert_snippet(
    plane_id: nu.StrArg,
    snippet: Snippet,
    *,
    index: nu.IntArg | None = None,
    cell_id: nu.StrArg | None = None,
) -> nu.Nu:
    """Add a cell from a snippet: its source as the prog, its name as the name.

    Yields:
        The cell id, as :func:`~nuspace.ops.cell.add_cell` does.
    """
    return add_cell(plane_id, snippet.source, cell_id=cell_id, name=snippet.name, index=index)
