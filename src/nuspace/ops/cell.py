"""Cell ops: write one, edit it, place it, drop it.

The only writer of the two facts that must agree about a cell's place: the
plane's ``cells`` list and the cell's ``plane``. Every op here that changes
one writes the other in the same commit. A cell stays on the plane it was
made on: nothing here moves one to another.

Every op here that writes a cell, or the plane's ``cells``, counts it on
the plane's ``version`` in the same commit, so following a plane's cells is
one key to watch.

A cell is addressed by its id alone. An op that needs its plane reads
``plane`` off it, inside its own bracket.

A cell's state is in the other store (States). Dropping a cell drops it
too, as a commit of its own after the structure one, in the order
:func:`~.utils.atomic_state` gives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nu.prog
import nu.tree
from nu.lang import ScalarQuery
from nuspace.shapes import Space
from nustd.ui.core import Ref as UiRef

from .kernel import interrupt_cell
from .read import cell_exists, cell_plane, plane_exists
from .state import drop_cell_state
from .utils import MintId, atomic, atomic_state, keep_order, snapshot


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.lang.runtime import Runtime


__all__ = [
    "HasUi",
    "add_cell",
    "remove_cell",
    "rename_cell",
    "reorder_cells",
    "set_cell_meta",
    "set_prog",
]


# In process: the host's own interpreter builds the term it inspects.
_BRACE = nu.prog.PyBrace()


def _draws(built: object) -> bool:
    """A constructed term holding a ui ref anywhere. A failed build draws nothing."""
    if not isinstance(built, nu.Nu):
        return False
    return nu.tree.find_first(built, lambda node: isinstance(node, UiRef)) is not None


class HasUi(ScalarQuery):
    """Whether ``prog`` draws: constructed, its tree holds a ui ref.

    Construction runs the snippet's module code in this process, offered the
    ``plane`` and ``cell`` a run offers. Source that does not construct reads
    False: as it stands it draws nothing.
    """

    def __init__(self, prog: nu.StrArg, plane_id: nu.StrArg, cell_id: nu.StrArg) -> None:
        super().__init__(prog, plane_id, cell_id)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        prog, plane, cell = children

        def thunk(rt: Runtime) -> object:
            scope = {"plane": plane(rt), "cell": cell(rt)}
            return _draws(_BRACE.construct(str(prog(rt)), scope=scope))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        prog, plane, cell = children

        async def athunk(rt: Runtime) -> object:
            scope = {"plane": await plane(rt), "cell": await cell(rt)}
            return _draws(await _BRACE.aconstruct(str(await prog(rt)), scope=scope))

        return athunk


def _write_prog(row: nu.Nu, prog: nu.StrArg, has_ui: nu.Nu) -> nu.Nu:
    """Set a cell's prog and the ``has_ui`` it implies, together, and count the write.

    ``version`` goes up by one per write, from 1, so a cell run recording an
    older one is running an older prog.
    """
    return (
        row.prog.set(prog)
        >> row.props.has_ui.set(has_ui)
        >> row.version.set(row.version.fallback(0) + 1)
    )


def _touch(plane_id: nu.StrArg) -> nu.Nu:
    """Count a write to one of the plane's cells on its ``version``. No bracket."""
    version = Space.planes[plane_id].version
    return version.set(version.fallback(0) + 1)


def _knowing_ui(
    prog: nu.StrArg,
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    build: Callable[[nu.Nu], nu.Nu],
) -> nu.Nu:
    """``build(has_ui)``, with :class:`HasUi` worked out before it runs.

    Constructing runs the prog's module code, which can take as long as its
    imports do. Outside the op's bracket, so the store's write lock is never
    held for it, and a retried commit does not construct again.
    """
    return nu.let(HasUi(prog, plane_id, cell_id), lambda has_ui: build(nu.Bool(has_ui)))


def _place(cells: nu.ListRef, cell_id: nu.StrArg, index: nu.IntArg | None) -> nu.Nu:
    """Put ``cell_id`` in a plane's ``cells`` at ``index``, the end when None, once."""
    put = cells.append(cell_id) if index is None else cells.insert(index, cell_id)
    return nu.IfDo(cells.contains(cell_id).not_(), put)


def _placeable(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Bool:
    """Whether ``cell_id`` may be written onto the plane: it is there, and the cell is new or its own."""
    on = cell_plane(cell_id)
    return plane_exists(plane_id).and_((on == "").or_(on == plane_id))


def add_cell(
    plane_id: nu.StrArg,
    prog: nu.StrArg,
    *,
    cell_id: nu.StrArg | None = None,
    name: nu.StrArg = "",
    index: nu.IntArg | None = None,
    made_by: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Write a cell onto a plane and place it at ``index``, in one commit.

    Args:
        plane_id: The plane. Nothing is written when it is missing.
        prog: The cell's source.
        cell_id: Its id, unique across the space. Minted when the term is
            evaluated when absent. Nothing is written when a cell of this id
            is on another plane.
        name: What to call it.
        index: Where in the plane's cells. The end when absent.
        made_by: Prop, the snippet it was made from, ``""`` for none.
        meta: Fields to merge into its meta.
        into: Set to the cell id in the commit, ``""`` when nothing was
            written, for a caller that needs a minted one: the record does
            not say which cell this call made.

    ``has_ui`` is worked out from ``prog`` (:class:`HasUi`). The props are
    written every time, so an existing cell given again takes
    the ones passed now.
    """

    def knowing(minted: nu.ObjectRef) -> nu.Nu:
        cid = nu.Str(minted)

        def commit(has_ui: nu.Nu) -> nu.Nu:
            placed = cell_writes(
                plane_id, cid, prog, has_ui, name=name, index=index, made_by=made_by, meta=meta
            )
            if into is None:
                return atomic(placed)
            return atomic(placed >> into.set(nu.If(cell_plane(cid) == plane_id, cid, "")))

        return _knowing_ui(prog, plane_id, cid, commit)

    # Minted ahead of the bracket, so has_ui is worked out outside it, and a
    # retried commit writes the same id again.
    return nu.let(MintId("c") if cell_id is None else cell_id, knowing)


def cell_writes(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    prog: nu.StrArg,
    has_ui: nu.Nu,
    *,
    name: nu.StrArg = "",
    index: nu.IntArg | None = None,
    made_by: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
) -> nu.Nu:
    """:func:`add_cell`'s writes for a cell id and ``has_ui`` already known. No bracket.

    The cell's row, its ``plane`` and its place in the plane's ``cells``,
    together. Nothing is written when the plane is missing or the cell is
    on another one.
    """
    row = Space.cells[cell_id]
    writes = (
        row.plane.set(plane_id)
        >> row.name.set(name)
        >> _write_prog(row, prog, has_ui)
        >> row.props.made_by.set(made_by)
    )
    if meta is not None:
        writes = writes >> row.meta.update(meta)
    placed = writes >> _place(Space.planes[plane_id].cells, cell_id, index) >> _touch(plane_id)
    return nu.IfDo(_placeable(plane_id, cell_id), placed)


def remove_cell(cell_id: nu.StrArg) -> nu.Nu:
    """Drop a cell: its live cell runs interrupted, off its plane, row deleted, then its state.

    Two commits, the row first. The other way round, a cell still on the
    plane (and its runs, still live until the interrupt lands) would read
    its state gone. This way the worst a crash between them leaves is state
    no cell points at.
    """
    row = atomic(
        nu.IfDo(
            cell_exists(cell_id),
            interrupt_cell(cell_id)
            >> Space.planes[cell_plane(cell_id)].cells.remove(cell_id, missing_ok=True)
            >> _touch(cell_plane(cell_id))
            >> Space.cells.del_item(cell_id),
        )
    )
    return row >> atomic_state(drop_cell_state(cell_id))


def rename_cell(cell_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a cell's name. A no-op when it is missing."""
    named = Space.cells[cell_id].name.set(name) >> _touch(cell_plane(cell_id))
    return atomic(nu.IfDo(cell_exists(cell_id), named))


def set_prog(cell_id: nu.StrArg, prog: nu.StrArg) -> nu.Nu:
    """Replace a cell's source, and its ``has_ui`` with it. Bumps its ``version``.

    Live cell runs keep running the prog they loaded: rerunning them is the
    reload service's. Nothing validates: a broken prog stores fine, and reads as not drawing.
    """
    row = Space.cells[cell_id]

    def knowing(plane: nu.ObjectRef) -> nu.Nu:
        def write(has_ui: nu.Nu) -> nu.Nu:
            written = _write_prog(row, prog, has_ui) >> _touch(cell_plane(cell_id))
            return atomic(nu.IfDo(cell_exists(cell_id), written))

        return _knowing_ui(prog, nu.Str(plane), cell_id, write)

    # Its plane is offered to the construction, as a run offers it.
    return nu.let(snapshot(cell_plane(cell_id)), knowing)


def set_cell_meta(cell_id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a cell's meta. A no-op when it is missing."""
    merged = Space.cells[cell_id].meta.update(fields) >> _touch(cell_plane(cell_id))
    return atomic(nu.IfDo(cell_exists(cell_id), merged))


def reorder_cells(plane_id: nu.StrArg, cell_ids: Sequence[nu.StrArg] | nu.Nu) -> nu.Nu:
    """Put a plane's cells in the order given.

    Ids not on the plane are skipped, and cells left out keep their place
    after the named ones, so a partial order is a move, not a truncation.
    """
    cells = Space.planes[plane_id].cells
    ordered = keep_order(cells, cell_ids, member=cells) >> _touch(plane_id)
    return atomic(nu.IfDo(plane_exists(plane_id), ordered))
