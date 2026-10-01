"""Cell ops: write one, edit it, place it, move it, drop it.

The only writer of the two facts that must agree about a plane's cells:
which ids are in ``cells`` and where they sit in ``order``. Every op here
fixes both in one commit.

A cell's state is in the other store (States). Dropping or moving a cell
touches it too, as commits of its own around the structure one, in the
order :func:`~.utils.atomic_state` gives.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nu.prog
import nu.tree
from nu.lang import ScalarQuery
from nuspace.shapes import Space, States
from nustd.ui.core import Ref as UiRef

from .kernel import interrupt_cell
from .read import cell_exists, plane_exists
from .state import drop_cell_state
from .utils import MintId, Then, atomic, atomic_state, keep_order


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.lang.runtime import Runtime


__all__ = [
    "HasUi",
    "add_cell",
    "move_cell",
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

    Builds the term itself rather than through a ``LoadNu``, so an op holding
    it still loads inside a program whose load binds a rewrite.
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
    version = nu.If(row.version.exists(), nu.ToInt(row.version) + nu.Int(1), nu.Int(1))
    return row.prog.set(prog) >> row.props.has_ui.set(has_ui) >> row.version.set(version)


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


def _place(order: nu.ListRef, cell_id: nu.StrArg, index: nu.IntArg | None) -> nu.Nu:
    """Put ``cell_id`` in ``order`` at ``index``, the end when None, once."""
    put = order.append(cell_id) if index is None else order.insert(index, cell_id)
    return nu.IfDo(nu.Not(order.contains(cell_id)), put)


def add_cell(
    plane_id: nu.StrArg,
    prog: nu.StrArg,
    *,
    cell_id: nu.StrArg | None = None,
    name: nu.StrArg = "",
    index: nu.IntArg | None = None,
    made_by: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
) -> nu.Nu:
    """Write a cell onto a plane and place it at ``index``, in one commit.

    Args:
        plane_id: The plane. Nothing is written when it is missing.
        prog: The cell's source.
        cell_id: Its id. Minted when the term is evaluated when absent.
        name: What to call it.
        index: Where in the plane's order. The end when absent.
        made_by: Prop, the snippet it was made from, ``""`` for none.
        meta: Fields to merge into its meta.

    ``has_ui`` is worked out from ``prog`` (:class:`HasUi`). The props are
    written every time, so an existing cell given again takes
    the ones passed now.

    Yields:
        The cell id, ``""`` when the plane is missing.
    """

    def write(cid: nu.ObjectRef, has_ui: nu.Nu) -> nu.Nu:
        placed = cell_writes(
            plane_id, nu.Str(cid), prog, has_ui, name=name, index=index, made_by=made_by, meta=meta
        )
        return Then(placed >> nu.IfDo(nu.Not(plane_exists(plane_id)), cid.set(nu.Str(""))), cid)

    def knowing(minted: nu.ObjectRef) -> nu.Nu:
        # The id the op yields is a copy made inside the bracket, so a retried
        # commit starts again from the minted id, whatever the last try set.
        def commit(has_ui: nu.Nu) -> nu.Nu:
            return atomic(nu.let(minted, lambda cid: write(cid, has_ui)))

        return _knowing_ui(prog, plane_id, nu.Str(minted), commit)

    # Minted ahead of the bracket, so has_ui is worked out outside it.
    return nu.let(MintId("c") if cell_id is None else nu.Str(cell_id), knowing)


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

    Nothing is written when the plane is missing.
    """
    plane = Space.planes[plane_id]
    row = plane.cells[cell_id]
    writes = row.name.set(name) >> _write_prog(row, prog, has_ui) >> row.props.made_by.set(made_by)
    if meta is not None:
        writes = writes >> row.meta.update(meta)
    return nu.IfDo(plane_exists(plane_id), writes >> _place(plane.order, cell_id, index))


def remove_cell(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Drop a cell: its live cell runs interrupted, out of order, row deleted, then its state.

    Two commits, the row first. The other way round, a cell still on the
    plane (and its runs, still live until the interrupt lands) would read
    its state gone. This way the worst a crash between them leaves is state
    no cell points at.
    """
    plane = Space.planes[plane_id]
    row = atomic(
        nu.IfDo(
            cell_exists(plane_id, cell_id),
            interrupt_cell(plane_id, cell_id)
            >> nu.IfDo(plane.order.contains(cell_id), plane.order.remove(cell_id))
            >> plane.cells.del_item(cell_id),
        )
    )
    return row >> atomic_state(drop_cell_state(plane_id, cell_id))


def rename_cell(plane_id: nu.StrArg, cell_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a cell's name. A no-op when it is missing."""
    row = Space.planes[plane_id].cells[cell_id]
    return atomic(nu.IfDo(cell_exists(plane_id, cell_id), row.name.set(name)))


def set_prog(plane_id: nu.StrArg, cell_id: nu.StrArg, prog: nu.StrArg) -> nu.Nu:
    """Replace a cell's source, and its ``has_ui`` with it. Bumps its ``version``.

    Live cell runs keep running the prog they loaded: rerunning them is the
    reload service's. Nothing validates: a broken prog stores fine, and reads as not drawing.
    """
    row = Space.planes[plane_id].cells[cell_id]
    return _knowing_ui(
        prog,
        plane_id,
        cell_id,
        lambda has_ui: atomic(
            nu.IfDo(cell_exists(plane_id, cell_id), _write_prog(row, prog, has_ui))
        ),
    )


def set_cell_meta(plane_id: nu.StrArg, cell_id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a cell's meta. A no-op when it is missing."""
    row = Space.planes[plane_id].cells[cell_id]
    return atomic(nu.IfDo(cell_exists(plane_id, cell_id), row.meta.update(fields)))


def reorder_cells(plane_id: nu.StrArg, cell_ids: Sequence[nu.StrArg] | nu.Nu) -> nu.Nu:
    """Put a plane's cells in the order given.

    Ids not on the plane are skipped, and cells left out keep their place
    after the named ones, so a partial order is a move, not a truncation.
    """
    plane = Space.planes[plane_id]
    return atomic(
        nu.IfDo(plane_exists(plane_id), keep_order(plane.order, cell_ids, member=plane.cells))
    )


def move_cell(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    to_plane_id: nu.StrArg,
    index: nu.IntArg | None = None,
) -> nu.Nu:
    """Move a cell to another plane, keeping its id, prog, props, meta and state.

    Its live cell runs are interrupted: they were loaded against the old plane.
    A no-op when either plane or the cell is missing, or the planes are the
    same (rearranging within a plane is :func:`reorder_cells`).

    Three commits: the state copied to the new plane, the row moved, the
    old state dropped. Copied first, so the cell never sits on the new plane
    without its state, and dropped last, from whichever plane the cell is
    not on: the old one once moved, the new one when the move was refused.
    """
    src, dst = Space.planes[plane_id], Space.planes[to_plane_id]
    movable = nu.And(
        nu.Ne(plane_id, to_plane_id),
        cell_exists(plane_id, cell_id),
        plane_exists(to_plane_id),
    )
    row = atomic(
        nu.IfDo(
            movable,
            interrupt_cell(plane_id, cell_id)
            >> dst.cells.set_item(cell_id, src.cells[cell_id].extract())
            >> _place(dst.order, cell_id, index)
            >> nu.IfDo(src.order.contains(cell_id), src.order.remove(cell_id))
            >> src.cells.del_item(cell_id),
        )
    )
    return (
        atomic_state(nu.IfDo(movable, _copy_state(plane_id, cell_id, to_plane_id)))
        >> row
        >> atomic_state(drop_cell_state(plane_id, cell_id) >> drop_cell_state(to_plane_id, cell_id))
    )


def _copy_state(plane_id: nu.StrArg, cell_id: nu.StrArg, to_plane_id: nu.StrArg) -> nu.Nu:
    """The cell's state written whole under ``to_plane_id``, when it has any. No bracket."""
    src = States.planes[plane_id].cells
    held = nu.And(States.planes.contains(plane_id), src.contains(cell_id))
    return nu.IfDo(held, States.planes[to_plane_id].cells.set_item(cell_id, src[cell_id].extract()))
