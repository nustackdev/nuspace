"""The desk ops: the desks in ``Web.desks`` and the items on each.

Every op is a bare term the caller brackets, as the core ops are::

    import nuspace.web as web

    nuspace.atomic(web.desks.create_desk("Runs", id="runs0001"))
    nuspace.atomic(web.desks.add_plane("runs0001", plane, {"run": "42"}))
    nuspace.atomic(web.desks.move_item("runs0001", item_id, to="favs0001"))

A desk is :class:`~nuspace.web.shapes.Desk`: a name and its entries, item id
to item, in order. Read back (:func:`get_desk`), it is ``{name, items}``, the
items in order with their ids, the shape the browser's ``Desk`` has. Placement
is ``before=`` or ``after=`` an id, neither for the end, as for planes and
cells. An id left out is minted: 8 chars of a-z and 0-9 for a desk, 6 for an
item, unique among the desks or within the desk.

Each op writes the Web store only. No plane on a desk is looked up, except
:func:`add_plane`'s. Writes raise when they cannot do what they say
(:mod:`nuspace.errors`); reads that may find nothing give NULL or ``[]``.

Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.lang import NULL
from nuspace.errors import Exists, Refused
from nuspace.shapes.space import Space
from nuspace.utils.checks import refuse, row_known
from nuspace.utils.placement import anchor_of, place

from ..shapes import Web
from .model import (
    KIND_PLANE,
    DeskIdProblem,
    DeskView,
    ItemIdProblem,
    ItemProblem,
    NewId,
    OrderMoves,
    ResetItem,
    SavedEntries,
    WriteProblem,
)


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "add_item",
    "add_plane",
    "create_desk",
    "delete_desk",
    "get_desk",
    "list_desks",
    "move_desk",
    "move_item",
    "remove_item",
    "rename_desk",
    "reset_item",
    "save_desk",
    "set_item",
    "write_items",
]


def _minted(id: nu.StrArg | None, size: int, write: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``write(id)``, with a fresh id of ``size`` chars when ``id`` is None."""
    if id is None:
        return nu.let(NewId(size), lambda minted: write(nu.Str(minted)))
    return write(nu.Str(id))


def _desk_known(desk_id: nu.StrArg) -> nu.Nu:
    """The desk is there.

    Raises:
        Missing: No desk with that id.
    """
    return row_known(Web.desks, desk_id, "desk")


def _item_known(desk_id: nu.StrArg, item_id: nu.StrArg) -> nu.Nu:
    """The desk is there and holds the item.

    Raises:
        Missing: No desk, or no item with that id on it.
    """
    return _desk_known(desk_id) >> row_known(Web.desks[desk_id].entries, item_id, "item")


def _item_shaped(item: nu.DictArg) -> nu.Nu:
    """The dict is a stored item, a plane item or a strip, no id.

    Raises:
        Refused: What is wrong with it, the first thing found.
    """
    problem = nu.Str(ItemProblem(item))
    return refuse(problem != "", Refused, problem)


def _anchor_known(
    rows: nu.Nu, before: nu.StrArg | None, after: nu.StrArg | None, what: str
) -> nu.Nu:
    """The anchor named, if any, is in ``rows``.

    Raises:
        Missing: No row with the anchor's id.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    return nu.Noop() if anchor is None else row_known(rows, anchor, what)  # type: ignore[arg-type]


def _to_end(rows: nu.Nu, id: nu.StrArg) -> nu.Nu:
    """Move ``id`` to the end of ordered ``rows``, nothing when it is last already."""
    last = nu.Str(rows.last())
    return nu.IfDo(last != id, rows.move(id, after=last))


def _move(rows: nu.Nu, id: nu.StrArg, before: nu.StrArg | None, after: nu.StrArg | None) -> nu.Nu:
    """Move ``id`` within ordered ``rows``, before or after an anchor, or to the end."""
    if before is not None:
        return rows.move(id, before=before)
    if after is not None:
        return rows.move(id, after=after)
    return _to_end(rows, id)


# --- Desks ------------------------------------------------------------------------------


def create_desk(
    name: nu.StrArg,
    *,
    id: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """A new, empty desk named ``name``, placed among the desks. Create only. Cost: O(1), a few keys.

    Raises:
        Refused: The id is not 8 chars of a-z and 0-9.
        Exists: A desk with that id is there.
        Missing: No desk with the anchor's id.
        TypeError: Both ``before`` and ``after``, at build.
    """

    def write(desk_id: nu.Str) -> nu.Nu:
        spelled = nu.Str(DeskIdProblem(desk_id))
        desk = Web.desks[desk_id]
        return (
            refuse(spelled != "", Refused, spelled)
            >> refuse(Web.desks.contains(desk_id), Exists, "desk ", desk_id, " exists")
            >> _anchor_known(Web.desks, before, after, "desk")
            >> place(Web.desks, desk_id, before=before, after=after, value=nu.Dict.of(name=name))
            >> desk.entries.set(nu.Dict.create())
        )

    return _minted(id, 8, write)


def rename_desk(desk_id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a desk's name. Cost: O(1), 1 key.

    Raises:
        Missing: No desk with that id.
    """
    return _desk_known(desk_id) >> Web.desks[desk_id].name.set(name)


def delete_desk(desk_id: nu.StrArg) -> nu.Nu:
    """Delete a desk and its items, a real delete. Its planes are left alone. Cost: O(items).

    Raises:
        Missing: No desk with that id.
    """
    return _desk_known(desk_id) >> Web.desks.del_item(desk_id)


def move_desk(
    desk_id: nu.StrArg, *, before: nu.StrArg | None = None, after: nu.StrArg | None = None
) -> nu.Nu:
    """Move a desk in the sidebar's order, before or after another desk, or last. Cost: O(1), a few keys.

    Raises:
        Missing: No desk with that id, or with the anchor's.
        TypeError: Both ``before`` and ``after``, at build.
    """
    return (
        _desk_known(desk_id)
        >> _anchor_known(Web.desks, before, after, "desk")
        >> _move(Web.desks, desk_id, before, after)
    )


def get_desk(desk_id: nu.StrArg) -> nu.Dict:
    """A desk as it is read: ``{name, items}``, its items in order, each with its ``id``. NULL when there is none.

    A read. Cost: O(items).
    """
    return nu.Dict(nu.If(Web.desks.contains(desk_id), DeskView(Web.desks[desk_id].extract()), NULL))


def list_desks() -> nu.List:
    """The desk ids in the sidebar's order, ``[]`` for none. A read. Cost: O(desks)."""
    return nu.List(nu.If(Web.desks.exists(), nu.list(Web.desks.keys()), []))


def save_desk(desk_id: nu.StrArg) -> nu.Nu:
    """Make every recent on the desk its original: what shows now is what the desk keeps. Cost: O(items).

    Raises:
        Missing: No desk with that id.
    """
    entries = Web.desks[desk_id].entries

    def write(saved: nu.Attr) -> nu.Nu:
        held = nu.Dict(saved)
        return nu.ForEachDo(
            nu.list(held.keys()), lambda i: entries.set_item(nu.Str(i), held[nu.Str(i)])
        )

    return _desk_known(desk_id) >> nu.let(SavedEntries(Web.desks[desk_id].extract()), write)


# --- Items ------------------------------------------------------------------------------


def add_item(
    desk_id: nu.StrArg,
    item: nu.DictArg,
    *,
    id: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Put a plane item or a strip on a desk, before or after an item, or last. Cost: O(1), a few keys.

    ``item`` is the stored item, no id: ``{kind: "plane", original,
    recent?}`` or ``{kind: "strip", columns}`` (:func:`~.model.item_problem`).

    Raises:
        Missing: No desk with that id, or no item with the anchor's.
        Refused: The id is not 6 chars of a-z and 0-9, or the dict is not an item.
        Exists: The desk holds an item with that id.
        TypeError: Both ``before`` and ``after``, at build.
    """
    entries = Web.desks[desk_id].entries

    def write(item_id: nu.Str) -> nu.Nu:
        spelled = nu.Str(ItemIdProblem(item_id))
        return (
            _desk_known(desk_id)
            >> refuse(spelled != "", Refused, spelled)
            >> refuse(entries.contains(item_id), Exists, "item ", item_id, " exists")
            >> _item_shaped(item)
            >> _anchor_known(entries, before, after, "item")
            >> place(entries, item_id, before=before, after=after, value=item)
        )

    return _minted(id, 6, write)


def add_plane(
    desk_id: nu.StrArg,
    plane: nu.StrArg,
    params: nu.DictArg | None = None,
    *,
    id: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Put a plane on a desk as a plane item, with ``params`` (none: ``{}``). Cost: O(1), a few keys.

    Raises:
        Missing: No desk, no plane, or no item with the anchor's id.
        Refused: The id is spelled wrong, or ``params`` is not str to str.
        Exists: The desk holds an item with that id.
        TypeError: Both ``before`` and ``after``, at build.
    """
    link = nu.Dict.of(plane=plane, params={} if params is None else params)
    item = nu.Dict.of(kind=KIND_PLANE, original=link)
    added = add_item(desk_id, item, id=id, before=before, after=after)
    return row_known(Space.planes, plane, "plane") >> added


def set_item(desk_id: nu.StrArg, item_id: nu.StrArg, item: nu.DictArg) -> nu.Nu:
    """Replace an item whole, in its place. Last write wins. Cost: O(1), 1 key.

    Raises:
        Missing: No desk, or no item with that id on it.
        Refused: The dict is not an item.
    """
    entries = Web.desks[desk_id].entries
    return _item_known(desk_id, item_id) >> _item_shaped(item) >> entries.set_item(item_id, item)


def remove_item(desk_id: nu.StrArg, item_id: nu.StrArg) -> nu.Nu:
    """Take an item off a desk. Its planes are left alone. Cost: O(1), a few keys.

    Raises:
        Missing: No desk, or no item with that id on it.
    """
    return _item_known(desk_id, item_id) >> Web.desks[desk_id].entries.del_item(item_id)


def move_item(
    desk_id: nu.StrArg,
    item_id: nu.StrArg,
    *,
    to: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Move an item within its desk, or to desk ``to``, before or after an item there, or last. Its id stays.

    Cost: O(1), a few keys.

    Raises:
        Missing: No desk, no such item, no desk ``to``, or no anchor there.
        Exists: Desk ``to`` holds an item with that id already.
        Refused: The anchor is the item itself.
        TypeError: Both ``before`` and ``after``, at build.
    """
    here = Web.desks[desk_id].entries
    target = desk_id if to is None else to
    there = Web.desks[target].entries
    anchor = anchor_of(before, after)
    itself = (
        nu.Noop()
        if anchor is None
        else refuse(
            nu.Str(anchor) == item_id, Refused, "item ", item_id, " cannot move next to itself"
        )
    )
    checks = (
        _item_known(desk_id, item_id)
        >> _desk_known(target)
        >> itself
        >> _anchor_known(there, before, after, "item")
    )

    def across(held: nu.Attr) -> nu.Nu:
        return (
            refuse(there.contains(item_id), Exists, "item ", item_id, " exists on desk ", target)
            >> here.del_item(item_id)
            >> place(there, item_id, before=before, after=after, value=nu.Dict(held))
        )

    within = _move(here, item_id, before, after)
    moved = nu.IfDo(nu.Str(target) == desk_id, within, nu.let(here[item_id].extract(), across))
    return checks >> moved


def reset_item(desk_id: nu.StrArg, item_id: nu.StrArg) -> nu.Nu:
    """Drop every recent of an item: it shows its originals again. Cost: O(1), 1 key.

    A strip whose panes then show one plane twice keeps the first
    (:func:`~.model.reset_item`).

    Raises:
        Missing: No desk, or no item with that id on it.
    """
    entries = Web.desks[desk_id].entries
    reset = ResetItem(entries[item_id].extract())
    return _item_known(desk_id, item_id) >> entries.set_item(item_id, reset)


def write_items(
    desk_id: nu.StrArg,
    sets: nu.DictArg,
    deletes: nu.ListArg[str] | None = None,
    order: nu.ListArg[str] | None = None,
) -> nu.Nu:
    """Several item writes on one desk: ``deletes``, then ``sets``, then ``order``. What the browser sends.

    ``sets`` is item id to item: an item there is replaced in its place, a
    new one goes last. ``deletes`` ids not on the desk are skipped (another
    tab got there first). ``order``, when given, puts the items it names
    first, in that order, the rest after (:func:`~.model.order_moves`);
    ids it names that are not there are skipped. Cost: O(items written +
    moves).

    Raises:
        Missing: No desk with that id.
        Refused: An item id spelled wrong, or an item not on the item shape.
    """
    entries = Web.desks[desk_id].entries
    write = nu.Dict.of(desk_id=desk_id, sets=sets, deletes=[] if deletes is None else deletes)
    problem = nu.Str(WriteProblem(write))
    gone = nu.ForEachDo(
        [] if deletes is None else deletes,
        lambda d: nu.IfDo(entries.contains(nu.Str(d)), entries.del_item(nu.Str(d))),
    )
    held = nu.Dict(sets)
    written = nu.ForEachDo(
        nu.list(held.keys()), lambda i: entries.set_item(nu.Str(i), held[nu.Str(i)])
    )
    steps = _desk_known(desk_id) >> refuse(problem != "", Refused, problem) >> gone >> written
    if order is None:
        return steps

    def one(move: nu.Attr) -> nu.Nu:
        m = nu.List(move)
        item, side, anchor = nu.Str(m[0]), nu.Str(m[1]), nu.Str(m[2])
        return nu.IfDo(
            side == "before", entries.move(item, before=anchor), entries.move(item, after=anchor)
        )

    moves = nu.ForEachDo(nu.List(OrderMoves(nu.list(entries.keys()), order)), one)
    return steps >> moves
