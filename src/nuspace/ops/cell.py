"""Cell ops: write one, edit it, place it, move it, drop it.

The only writer of the two facts that must agree about a plane's cells:
which ids are in ``cells`` and where they sit in ``order``. Every op here
fixes both in one commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nu.prog
import nu.tree
from nu.lang import ScalarQuery
from nuspace.shapes import Space
from nustd.ui.core import Ref as UiRef

from .kernel import stop_runs
from .read import cell_exists, plane_exists
from .utils import MintId, atomic, binding, keep_order


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


def _write_prog(row: nu.Nu, plane_id: nu.StrArg, cell_id: nu.StrArg, prog: nu.StrArg) -> nu.Nu:
    """Set a cell's prog and the ``has_ui`` it implies, together."""
    return row.prog.set(prog) >> row.props.has_ui.set(HasUi(prog, plane_id, cell_id))


def _place(order: nu.ListRef, cell_id: nu.StrArg, index: nu.IntArg | None) -> nu.Nu:
    """Put ``cell_id`` in ``order`` at ``index``, the end when None, once."""
    put = order.append(cell_id) if index is None else order.insert(index, cell_id)
    return nu.IfDo(nu.Not(order.contains(cell_id)), put)


def _stop_cell(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Ask the cell's live runs to stop. No bracket."""
    return stop_runs(lambda run: nu.And(nu.Eq(run.plane, plane_id), nu.Eq(run.cell, cell_id)))


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

    def write(cid_name: str) -> nu.Nu:
        cid = nu.StrAttrRef(cid_name)
        plane = Space.planes[plane_id]
        row = plane.cells[cid]
        writes = (
            row.name.set(name)
            >> _write_prog(row, plane_id, cid, prog)
            >> row.props.made_by.set(made_by)
        )
        if meta is not None:
            writes = writes >> row.meta.update(meta)
        return nu.IfDo(
            plane_exists(plane_id), writes >> _place(plane.order, cid, index)
        ) >> nu.IfDo(nu.Not(plane_exists(plane_id)), nu.SetCmd(cid, nu.Str("")))

    value = MintId("c") if cell_id is None else nu.Str(cell_id)
    return atomic(binding(value, write, tag="c"))


def remove_cell(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Drop a cell: its live runs asked to stop, out of order, row deleted."""
    plane = Space.planes[plane_id]
    return atomic(
        nu.IfDo(
            cell_exists(plane_id, cell_id),
            _stop_cell(plane_id, cell_id)
            >> nu.IfDo(plane.order.contains(cell_id), plane.order.remove(cell_id))
            >> plane.cells.del_item(cell_id),
        )
    )


def rename_cell(plane_id: nu.StrArg, cell_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a cell's name. A no-op when it is missing."""
    row = Space.planes[plane_id].cells[cell_id]
    return atomic(nu.IfDo(cell_exists(plane_id, cell_id), row.name.set(name)))


def set_prog(plane_id: nu.StrArg, cell_id: nu.StrArg, prog: nu.StrArg) -> nu.Nu:
    """Replace a cell's source, and its ``has_ui`` with it.

    Nothing validates: a broken prog stores fine, and reads as not drawing.
    """
    row = Space.planes[plane_id].cells[cell_id]
    return atomic(
        nu.IfDo(cell_exists(plane_id, cell_id), _write_prog(row, plane_id, cell_id, prog))
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

    Its live runs are asked to stop: they were loaded against the old plane.
    A no-op when either plane or the cell is missing, or the planes are the
    same (rearranging within a plane is :func:`reorder_cells`).
    """
    src, dst = Space.planes[plane_id], Space.planes[to_plane_id]
    return atomic(
        nu.IfDo(
            nu.And(
                nu.Ne(plane_id, to_plane_id),
                cell_exists(plane_id, cell_id),
                plane_exists(to_plane_id),
            ),
            _stop_cell(plane_id, cell_id)
            >> dst.cells.set_item(cell_id, src.cells[cell_id].extract())
            >> _place(dst.order, cell_id, index)
            >> nu.IfDo(src.order.contains(cell_id), src.order.remove(cell_id))
            >> src.cells.del_item(cell_id),
        )
    )
