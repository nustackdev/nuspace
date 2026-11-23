"""The layout ops: the items of a web plane's layout, ``Web.planes[plane].layout``.

Every op but :func:`transfer_cell` is a bare term the caller brackets, as
the desk ops are::

    import nuspace.web as web

    nuspace.atomic(web.layout.add_item(plane, {"kind": "cell", "cell": c}, after=item_id))
    nuspace.atomic(web.layout.move_item(plane, item_id, before=other))
    nuspace.atomic(web.layout.place_cell(plane, c, into=strip_id, column=1, index=0))
    web.layout.transfer_cell(c, other_plane, after=item_id)   # two commits, brackets itself

A layout is item id to item, in drawing order: a cell item ``{kind: "cell",
cell}`` or a strip ``{kind: "strip", columns}``, each column ``{cells,
share}`` (:func:`~.model.item_problem`). Read back (:func:`get_layout`), it
is the list of items as drawn, each with its ``id``, fixed up against the
plane's cells (:func:`~.model.layout_view`). Placement is ``before=`` or
``after=`` an item id, neither for the end, as for desks. An id left out is
drawn from the item's first cell, as the fill draws one: 6 chars of a-z and
0-9, free in the layout, never random, so a retried commit writes the same.

**Every op fills first.** The read shows cells the store may lack (a cell
on the plane in no item, drawn after its predecessor's item). Before its
own change, every op stores those, at the spots and with the ids the read
gave them (:func:`~.model.fills`), one O(items) pass. So an item the
browser saw is always a stored item, there to anchor on or to change.

**One item a cell.** A cell sits in one item. An op writing one item
(:func:`add_item`, :func:`set_item`, :func:`place_cell`) takes its cells out
of every other item first, by the strip rules, so a drag of one cell onto
another is one op. :func:`write_items` states a whole change and is checked
whole: a cell in two items after it is refused.

**Checks.** Every item written is on the item shape; every cell it holds is
on the plane (in ``Plane.cells``: not removed, not transferred out). The
plane is live and on the web. Nothing else is looked up. Writes raise when
they cannot do what they say (:mod:`nuspace.errors`).

Each op writes the Web store only, but for :func:`transfer_cell`, whose first
commit is Space's.

**One host call an op.** Each op is worked out whole in python
(:func:`~.model.plan`): the fill, its checks, its writes. Its term is the
plane check, that call, and one loop applying the writes, the same for
every op. Anchors and ``into`` may be terms read at run time, ``""`` for
none: a browser event hands them over as such. The term stays small, which
matters: a tab's pane holds one arm per layout event, and a tab's whole term
is compiled when web starts.

Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

import nu
from nuspace.ops import cell as cell_ops
from nuspace.ops.brackets import atomic
from nuspace.shapes.space import Space
from nuspace.utils import keys_of
from nuspace.utils.placement import anchor_of

from ..shapes import Web
from .model import LayoutView, Plan


__all__ = [
    "add_item",
    "get_layout",
    "move_item",
    "place_cell",
    "remove_item",
    "set_item",
    "transfer_cell",
    "write_items",
]


def _layout(plane: nu.StrArg) -> nu.Nu:
    return Web.planes[plane].layout


def _stored(plane: nu.StrArg) -> nu.Nu:
    """The stored layout, item id to item in order, ``{}`` when it was never written. A read."""
    layout = _layout(plane)
    return nu.If(layout.exists(), layout.extract(), nu.Literal({}))


def _cells(plane: nu.StrArg) -> nu.Nu:
    """The plane's cell ids, in ``cells`` order: what is on it."""
    return keys_of(Space.planes[plane].cells)


def _run(plane: nu.StrArg, op: str, **args: object) -> nu.Nu:
    """Layout op ``op`` on ``plane``: worked out by :func:`~.model.plan`, then written in order.

    Every op is this one shape: a few reads, one host call (which raises
    the op's refusal, and so writes nothing), one loop applying the writes.
    Kept small on purpose. O(items + cells).
    """
    layout = _layout(plane)
    row = nu.Dict.of(
        id=plane,
        known=Space.planes.contains(plane),
        removed=Space.planes[plane].removed_at.exists(),
        on_web=Web.planes.contains(plane),
    )

    def write(held: nu.Attr) -> nu.Nu:
        w = nu.List(held)
        verb, item_id, value, anchor = nu.Str(w[0]), nu.Str(w[1]), w[2], nu.Str(w[3])
        return nu.SwitchDo(
            verb,
            {
                "set": layout.set_item(item_id, value),
                "del": layout.del_item(item_id),
                "before": layout.insert_before(anchor, item_id, value),
                "after": layout.insert_after(anchor, item_id, value),
            },
        )

    planned = Plan(op, row, _stored(plane), _cells(plane), nu.Dict.of(**args))
    # Made after the plan read the row: made first, it would put a plane not on the web on it.
    made = layout.init(nu.Dict.create())
    return nu.let(planned, lambda held: made >> nu.ForEachDo(nu.List(held), write))


def _anchors(before: nu.StrArg | None, after: nu.StrArg | None) -> dict[str, object]:
    """The anchors as the plan takes them. Both given as values raises at build."""
    if not isinstance(before, nu.Nu) and not isinstance(after, nu.Nu):
        anchor_of(before or None, after or None)
    return {"before": before, "after": after}


# --- Reads -------------------------------------------------------------------------------


def get_layout(plane: nu.StrArg) -> nu.List:
    """The layout as it is drawn: its items in order, each with its ``id``, fixed up. A read.

    One cell item per cell, in ``cells`` order, for a plane whose layout was
    never written; ``[]`` for a plane with no cells or no row. Cost:
    O(items + cells).
    """
    return nu.List(LayoutView(_stored(plane), _cells(plane)))


# --- Items -------------------------------------------------------------------------------


def add_item(
    plane: nu.StrArg,
    item: nu.DictArg,
    *,
    id: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Put a cell item or a strip in a plane's layout, before or after an item, or last. Cost: O(items).

    ``item`` is the stored item, no id: ``{kind: "cell", cell}`` or ``{kind:
    "strip", columns}`` (:func:`~.model.item_problem`). Placed first, then
    its cells are taken out of every other item, by the strip rules: the
    anchor may be an item that empties.

    Raises:
        Missing: No plane, the plane not on the web, or no item with the anchor's id.
        Removed: The plane is removed.
        Refused: The id is spelled wrong, the dict is not an item, a cell
            not on the plane.
        Exists: The layout holds an item with that id.
        TypeError: Both ``before`` and ``after``, at build.
        ValueError: Both, given as terms, at run time.
    """
    return _run(plane, "add", item=item, id=id, **_anchors(before, after))


def set_item(plane: nu.StrArg, item_id: nu.StrArg, item: nu.DictArg) -> nu.Nu:
    """Replace an item whole, in its place. Last write wins. Cost: O(items).

    Its cells are then taken out of every other item, by the strip rules: a
    cell dropped beside another to make a strip is one set.

    Raises:
        Missing: No plane, the plane not on the web, or no item with that id.
        Removed: The plane is removed.
        Refused: The dict is not an item, a cell not on the plane.
    """
    return _run(plane, "set", id=item_id, item=item)


def remove_item(plane: nu.StrArg, item_id: nu.StrArg) -> nu.Nu:
    """Take an item out of a layout. Cost: O(items).

    Its cells stay on the plane: still in no item, the read draws each as its
    own cell item after its predecessor's. Removing a cell is the core op's.

    Raises:
        Missing: No plane, the plane not on the web, or no item with that id.
        Removed: The plane is removed.
    """
    return _run(plane, "remove", id=item_id)


def move_item(
    plane: nu.StrArg,
    item_id: nu.StrArg,
    *,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Move an item within its layout, before or after an item, or last. Its id stays. Cost: O(items).

    What the browser's reorder writes on a web plane, in place of ``cell.move``.

    Raises:
        Missing: No plane, the plane not on the web, no such item, or no anchor.
        Removed: The plane is removed.
        Refused: The anchor is the item itself.
        TypeError: Both ``before`` and ``after``, at build.
        ValueError: Both, given as terms, at run time.
    """
    return _run(plane, "move", id=item_id, **_anchors(before, after))


def write_items(
    plane: nu.StrArg,
    sets: nu.DictArg,
    deletes: nu.ListArg[str] | None = None,
    order: nu.ListArg[str] | None = None,
) -> nu.Nu:
    """Several item writes on one layout: ``deletes``, then ``sets``, then ``order``. Cost: O(items).

    What a drag that changes more than one item sends (a cell out of one
    strip and into another, a strip made from two cell items): checked
    whole, so a cell moving between items is never in two, nor in none.
    ``sets`` is item id to item: an item there is replaced in its place, a
    new one goes last. ``deletes`` ids not in the layout are skipped.
    ``order``, when given, puts the items it names first, in that order, the
    rest after (:func:`~nuspace.web.items.order_moves`); ids it names that
    are not there are skipped.

    Raises:
        Missing: No plane, or the plane not on the web.
        Removed: The plane is removed.
        Refused: An item id spelled wrong, an item not on the item shape, a
            cell not on the plane or in two items.
    """
    gone = [] if deletes is None else deletes
    return _run(plane, "write", sets=sets, deletes=gone, order=order)


# --- One cell ----------------------------------------------------------------------------


def place_cell(
    plane: nu.StrArg,
    cell: nu.StrArg,
    *,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    into: nu.StrArg | None = None,
    column: nu.IntArg | None = None,
    index: nu.IntArg | None = None,
    id: nu.StrArg | None = None,
) -> nu.Nu:
    """Put a cell of the plane at a spot in its layout, out of wherever it was. Cost: O(items).

    Either:

    - its own cell item, ``id`` (drawn from the cell when left out), ``before`` or
      ``after`` an item, or last. Placed first, then the cell is taken out
      of every other item, by the strip rules (:func:`~.model.taken_out`):
      the anchor may be the item it leaves;
    - or ``into`` a strip, in its column ``column`` at ``index`` among that
      column's cells. The cell is taken out of every item first, the strip
      included, so ``index`` counts the column without it; past the end is
      the end. The shares stay.

    Raises:
        Missing: No plane, the plane not on the web, no anchor, no item ``into``.
        Removed: The plane is removed.
        Refused: The cell is not on the plane, the id is spelled wrong,
            ``into`` is not a strip or has no such column.
        Exists: The layout holds an item with that id.
        TypeError: ``into`` with ``before`` or ``after``, or without
            ``column`` and ``index``; both ``before`` and ``after``. At build.
        ValueError: ``into`` with an anchor, or both anchors, given as terms, at run time.
    """
    terms = any(isinstance(x, nu.Nu) for x in (before, after, into))
    named = into is not None and (isinstance(into, nu.Nu) or into != "")
    if not terms and named and (before is not None or after is not None):
        msg = "place_cell takes into= or before= / after=, not both"
        raise TypeError(msg)
    if named and (column is None or index is None):
        msg = "place_cell into= takes column= and index="
        raise TypeError(msg)
    spot = {"into": into, "column": column, "index": index, **_anchors(before, after)}
    return _run(plane, "place", on=plane, cell=cell, new_id=id, **spot)


def transfer_cell(
    cell: nu.StrArg,
    plane: nu.StrArg,
    *,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    into: nu.StrArg | None = None,
    column: nu.IntArg | None = None,
    index: nu.IntArg | None = None,
) -> nu.Nu:
    """Bring a cell to ``plane`` and place it in that plane's layout. Brackets itself: two commits.

    First, when the cell is on another plane, ``nuspace.cell.transfer(cell,
    plane)``, one Space commit: the cell lands at the end of the target's
    ``cells``. A cell on ``plane`` already is only placed. Then :func:`place_cell` on
    the target, one Web commit, at the spot given (``before`` / ``after`` an
    item, ``into`` a strip column at ``index``, or last). Space and Web are
    two stores, so two commits: a place that fails leaves the cell
    transferred, drawn after its predecessor's item (the last cell's) by
    the read's fix-up, and the error raises. The old plane's layout keeps
    its item: the cell is skipped there, and comes back to it when
    transferred back.

    Raises:
        What ``nuspace.cell.transfer`` raises (nothing written), then what
        :func:`place_cell` raises (the transfer stays).
    """
    placed = place_cell(
        plane, cell, before=before, after=after, into=into, column=column, index=index
    )
    elsewhere = nu.Str(atomic(Space.cells[cell].plane.fallback(""))) != plane
    return nu.IfDo(elsewhere, atomic(cell_ops.transfer(cell, plane))) >> atomic(placed)
