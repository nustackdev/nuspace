"""The layout ops: :func:`get` and :func:`set` around one pure host, and :func:`transfer`.

``Web.planes[plane].layout`` is internal: nothing reads or writes the raw
slot but :func:`get` and :func:`set`. Code reading a layout calls
:func:`get`::

    import nuspace.web as web

    nu.let([], lambda rows: nuspace.atomic(web.layout.get(plane, into=rows)) >> ...)
    nuspace.atomic(web.layout.set(plane, rows))
    web.layout.transfer(cell, other_plane, rows)   # two commits, brackets itself

Both are plain kv terms around :data:`~.model.LayoutReconcile`: two reads (the
slot and the plane's cells), one host call, at most one write. One commit
each, O(that plane).

Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

import nu
from nuspace.errors import Missing, Refused
from nuspace.ops import cell as cell_ops
from nuspace.ops.brackets import atomic
from nuspace.shapes.space import Space
from nuspace.utils import keys_of
from nuspace.utils.checks import live, refuse

from ..shapes import Web
from .model import LayoutReconcile, RowsProblem


__all__ = ["get", "set", "transfer"]


def _slot(plane: nu.StrArg) -> nu.Nu:
    return Web.planes[plane].layout


def _cells(plane: nu.StrArg) -> nu.Nu:
    """The plane's cell ids: membership, their order means nothing to the layout."""
    return keys_of(Space.planes[plane].cells)


def get(plane: nu.StrArg, *, into: nu.Ref) -> nu.Nu:
    """The layout, reconciled with the plane's cells, set into ``into``. Heals the slot. Bare term.

    ``let x = LayoutReconcile(slot, cells)``, the slot written only when ``x``
    differs from it, and only on a plane on the web (a missing slot reads
    ``[]``). 0 or 1 write. A plane with no cells and no slot reads ``[]``.
    Cost: O(rows + cells).
    """
    slot = _slot(plane)

    def reconciled(held: nu.ObjectRef) -> nu.Nu:
        def heal(x: nu.ObjectRef) -> nu.Nu:
            changed = Web.planes.contains(plane).and_(nu.List(x) != nu.List(held))
            return nu.IfDo(changed, slot.set(nu.List(x))) >> into.set(nu.List(x))

        return nu.let(LayoutReconcile(held, _cells(plane)), heal)

    return nu.let(slot.fallback([]), reconciled)


def set(plane: nu.StrArg, rows: nu.ListArg[dict]) -> nu.Nu:
    """Write a plane's layout whole: ``rows`` checked on the shape, then reconciled with its cells. Bare term.

    Reconciled on the way in, so a stale view never writes a broken layout:
    a cell no longer on the plane is dropped, one in two places stays with
    its first holder, one in no row goes last. Last write wins. Cost:
    O(rows + cells).

    Raises:
        Missing: No plane, or the plane not on the web.
        Removed: The plane is removed.
        Refused: ``rows`` off the shape (:func:`~.model.rows_problem`).
    """
    on_web = Web.planes.contains(plane).not_()
    checks = live(Space.planes, plane, "plane") >> refuse(
        on_web, Missing, "plane ", plane, " is not on the web"
    )

    def write(said: nu.ObjectRef) -> nu.Nu:
        shaped = refuse(nu.Str(said) != "", Refused, said)
        return shaped >> _slot(plane).set(nu.List(LayoutReconcile(rows, _cells(plane))))

    return checks >> nu.let(RowsProblem(rows), write)


def transfer(cell: nu.StrArg, plane: nu.StrArg, rows: nu.ListArg[dict]) -> nu.Nu:
    """Bring a cell to ``plane``, then write that plane's layout. Brackets itself: two commits.

    ``rows`` are the target's, the cell already in place. First
    ``nuspace.cell.transfer(cell, plane)``, one Space commit, then
    :func:`set` on the target, one Web commit. A set that fails leaves the
    cell transferred, and the target's next :func:`get` puts it last. The
    old plane heals on its own next :func:`get`.

    Raises:
        What ``nuspace.cell.transfer`` raises (nothing written), then what
        :func:`set` raises (the transfer stays).
    """
    return atomic(cell_ops.transfer(cell, plane)) >> atomic(set(plane, rows))
