"""Extension ops: create a registered Plane, insert a snippet.

Planes and snippets are registry entries, registered by the host at open.
Core ships none privileged: a third party registers the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import nu
from nuspace.shapes import ROOT

from .cell import HasUi, add_cell, cell_writes
from .plane import plane_icon, plane_writes
from .utils import MintId, atomic


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["TEXT", "Plane", "Snippet", "create_plane", "insert_snippet"]


#: The name reserved for the text snippet, see :class:`Snippet`.
TEXT = "text"


@dataclass(frozen=True)
class Plane:
    """A plane ``+`` can create: data, seeded as is. No build hook.

    Everything it does lives in its cells: args, forms, lists, background
    work. Creating one only seeds it.

    Args:
        name: Registry key, and what the planes created from it record as
            ``made_by``.
        label: What the picker shows, and a new plane's default name.
        icon: A lucide icon name, ``""`` for the default. ``"lucide:<name>"``
            and ``"emoji:<char>"`` work too. A new plane's ``meta.icon``
            starts as it, unless ``meta`` sets one.
        description: One line for the picker.
        meta: What a new plane's meta starts as.
        cells: ``(name, source)`` per cell, in order.
        children: Planes seeded under it, the same shape, in order.
        backend: Keyword, required. The backend a plane created from it
            runs on, by registered name. Picked by the kind of work its cells
            do: many awaiting tasks run well on ``async``, sync code on ``mp``.

    Raises:
        ValueError: ``backend`` is empty.
    """

    name: str
    label: str
    icon: str = ""
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    cells: tuple[tuple[str, str], ...] = ()
    children: tuple[Plane, ...] = ()
    backend: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.backend:
            msg = f"Plane {self.name!r}: backend is required, eg mp or async"
            raise ValueError(msg)


@dataclass(frozen=True)
class Snippet:
    """Source for one cell, offered from the ``/`` menu.

    The name :data:`TEXT` is reserved for the text snippet. Its cells are
    the text cells the plane writes like a document: typing on an empty line
    starts one, Enter in the title starts one at the top with the text after
    the caret, Cmd+Enter in one starts the next below, and Backspace in an
    empty one removes it. With no snippet under that name, typing opens the
    ``/`` menu and the rest is off.

    Args:
        name: Registry key, the new cell's name, and what the cells made
            from it record as ``props.made_by``.
        label: What the menu shows.
        source: The cell's prog.
        search: What searching one of its cells means, None when it has no
            content to search. ``search(query, plane, cell)`` returns a term
            yielding that cell's hits, a list of ``{plane, cell, excerpt}``,
            ``[]`` for none. It runs inside a search's run, on a worker, so it
            is named there by module and qualified name: a module level
            function, never a lambda or a closure.
    """

    name: str
    label: str
    source: str
    search: Callable[[nu.Nu, nu.Nu, nu.Nu], nu.Nu] | None = None

    def __post_init__(self) -> None:
        if self.search is not None and "<" in getattr(self.search, "__qualname__", "<"):
            msg = f"Snippet {self.name!r}: search must be a module level function"
            raise ValueError(msg)


class _Seeding(nu.Shape):
    """What :func:`create_plane` works out before its bracket, under names fixed at build."""

    ids = nu.DictRef.slot(str)
    ui = nu.DictRef.slot(bool)


def create_plane(
    spec: Plane,
    *,
    parent: nu.StrArg = ROOT,
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
        parent: The tree node to hang it under, ``ROOT`` or a plane id.
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

    ``into`` is :func:`~nuspace.ops.cell.add_cell`'s.
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
