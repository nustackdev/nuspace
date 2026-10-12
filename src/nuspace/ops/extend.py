"""Extension ops: create a registered Plane, insert a snippet.

The Planes and snippets themselves are :mod:`nuspace.ext` specs, registered
by the host at open. Core ships none privileged: a third party registers the
same way.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .cell import HasUi, add_cell, cell_writes
from .plane import plane_icon, plane_writes
from .utils import MintId, atomic


if TYPE_CHECKING:
    from nuspace.ext import Plane, Snippet


__all__ = ["create_plane", "insert_snippet"]


class _Seeding(nu.Shape):
    """What :func:`create_plane` works out before its bracket, under names fixed at build."""

    ids = nu.DictRef.slot(str)
    ui = nu.DictRef.slot(bool)


def create_plane(
    spec: Plane,
    *,
    parent: nu.StrArg = "",
    name: nu.StrArg | None = None,
    plane_id: nu.StrArg | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Create a plane from ``spec``: drawn, its cells in order, its children under it.

    One commit: the plane, its cells and its children land together or not
    at all, so no reader ever sees a plane without its cells. Every id and
    every cell's ``has_ui`` are worked out first, outside the bracket, the
    way :func:`~nuspace.ops.cell.add_cell` does.

    Args:
        spec: The registered Plane. It runs on ``spec.backend``, and each
            child on its own spec's.
        parent: The plane to hang it under, ``""`` for the top level.
        name: What to call it. ``spec.label`` when absent.
        plane_id: Its id. Minted when absent. Children always mint theirs.
        into: Set to the new plane's id once the commit landed, for a caller
            that needs a minted one: the record does not say which plane
            this call made.
    """
    pid = _Seeding.ids["p0"]
    first: list[nu.Nu] = [pid.set(MintId("p") if plane_id is None else plane_id)]
    label = spec.label if name is None else name
    writes = [atomic(_seeded(spec, pid, parent, label, first))]
    if into is not None:
        writes.append(into.set(nu.Str(pid)))
    return nu.Frame(_Seeding, nu.Sequential(*first, *writes), ids={}, ui={})


def _seeded(
    spec: Plane,
    plane_id: nu.Nu,
    parent: nu.StrArg,
    name: nu.StrArg,
    first: list[nu.Nu],
) -> nu.Nu:
    """``spec``'s writes under ``plane_id``, children included. No bracket.

    What has to be known before the bracket (the cells' and children's ids,
    each cell's ``has_ui``) is worked out into :class:`_Seeding` by the
    writes appended to ``first``, in the order it is needed.
    """
    meta = dict(spec.meta)
    if spec.icon and "icon" not in meta:
        meta["icon"] = plane_icon(spec.icon)
    writes = [
        plane_writes(
            plane_id,
            backend=spec.backend,
            name=name,
            parent=parent,
            ui=True,
            made_by=spec.name,
            meta=meta,
        )
    ]
    for cell, source in spec.cells:
        key = f"c{len(first)}"
        cid, ui = _Seeding.ids[key], _Seeding.ui[key]
        first += [cid.set(MintId("c")), ui.set(HasUi(source, plane_id, cid))]
        writes.append(cell_writes(plane_id, cid, source, ui, name=cell))
    for child in spec.children:
        pid = _Seeding.ids[f"p{len(first)}"]
        first.append(pid.set(MintId("p")))
        writes.append(_seeded(child, pid, plane_id, child.label, first))
    return nu.Sequential(*writes)


def insert_snippet(
    plane_id: nu.StrArg,
    snippet: Snippet,
    *,
    index: nu.IntArg | None = None,
    cell_id: nu.StrArg | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Add a cell from a snippet: its source as the prog, its name as the name and ``made_by``.

    ``into`` is :func:`~nuspace.ops.cell.add_cell`'s: set to the new cell's
    id in the commit, ``""`` when nothing was written. A program that goes
    on to write the cell holds it in a ``nu.let`` slot and hands the slot to
    the snippet's ops::

        nu.let("", lambda cell: (
            ops.insert_snippet(plane, prose.SNIPPET, into=cell)
            >> prose.set_text(cell, "Water the basil")
        ))
    """
    return add_cell(
        plane_id,
        snippet.source,
        cell_id=cell_id,
        name=snippet.name,
        index=index,
        made_by=snippet.name,
        into=into,
    )
