"""The plane layout in plain python, and the two hosts the layout ops and the pane run it through.

- Checks: :func:`item_problem` (one stored item), :func:`write_problem` (one
  layout's items write), :func:`cells_problem` (the cells a write places),
  :func:`off_plane` (the cells of one item), :func:`column_problem` (a
  strip column a cell goes into), each ``""`` for nothing wrong.
- Reads: :func:`layout_view` (:data:`LayoutView`), the layout as it is
  drawn, fixed up.
- Writes: :func:`fills` (what the fix-up shows and the store lacks),
  :func:`taken_out` (cells out of every item), :func:`put_in` (a cell into a
  strip column), and :func:`plan` (:data:`Plan`), one whole layout op worked
  out here: its checks and the writes it makes, so an op's term is one host
  call and one loop applying its writes, whatever the op.

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping

import nu
from nuspace.errors import Exists, Missing, Refused, Removed
from nuspace.web.items import (
    ID_CHARS,
    fraction,
    ids,
    item_id_problem,
    keys_problem,
    listed,
    order_moves,
    rescaled,
    shares_problem,
)


__all__ = [
    "KIND_CELL",
    "KIND_STRIP",
    "OPS",
    "LayoutView",
    "Plan",
    "cells_problem",
    "column_problem",
    "fills",
    "item_cells",
    "item_problem",
    "layout_view",
    "off_plane",
    "plan",
    "put_in",
    "taken_out",
    "write_problem",
]


# A layout is stored as ``WebPlane.layout``: item id to item, in drawing
# order. An item is a cell item or a strip, its id the key, never in the
# value. Read back, it is a list of items, each with its ``id``, fixed up
# against the plane's cells (:func:`layout_view`).

#: The two kinds of item.
KIND_CELL = "cell"
KIND_STRIP = "strip"


# --- Checks ------------------------------------------------------------------------------


def _column_problem(column: object, at: str) -> str:
    said = keys_problem(column, {"cells", "share"}, at)
    if said:
        return said
    cells = column["cells"]  # type: ignore[index]
    if not ids(cells) or not cells or "" in cells:
        return f"{at} cells is not a list of cell ids"
    if not fraction(column["share"]):  # type: ignore[index]
        return f"{at} share is not a number in (0, 1]"
    return ""


def _strip_problem(strip: Mapping, at: str) -> str:
    columns = strip["columns"]
    if not isinstance(columns, list) or not columns:
        return f"{at} has no columns"
    for c, column in enumerate(columns):
        said = _column_problem(column, f"{at} column {c}")
        if said:
            return said
    said = shares_problem(columns, at)
    if said:
        return said
    held = [cell for column in columns for cell in column["cells"]]
    if len(held) < 2:
        return f"{at} has one cell, a cell item then"
    twice = sorted({c for c in held if held.count(c) > 1})
    return f"{at} holds cell {twice[0]} twice" if twice else ""


def item_problem(item: object) -> str:
    """Why ``item`` is not a stored item, ``""`` when it is. Plain python, what :data:`ItemProblem` runs.

    A cell item ``{kind: "cell", cell}`` or a strip ``{kind: "strip",
    columns}``, no id (the id is its key). A strip has columns ``{cells,
    share}``: ``cells`` a non-empty list of cell ids, stacked in the
    column, ``share`` a number in ``(0, 1]``, the columns' shares summing
    to 1. A strip holds two cells or more, none twice. No cell is looked up.
    """
    if not isinstance(item, Mapping):
        return "item is not a dict"
    kind = item.get("kind")
    if kind == KIND_CELL:
        said = keys_problem(item, {"kind", "cell"}, "item")
        if said:
            return said
        cell = item["cell"]
        return "" if isinstance(cell, str) and cell else "item cell is not a cell id"
    if kind == KIND_STRIP:
        said = keys_problem(item, {"kind", "columns"}, "item")
        return said or _strip_problem(item, "strip")
    return f"item kind is not {KIND_CELL!r} or {KIND_STRIP!r}"


def item_cells(item: Mapping) -> list[str]:
    """The cells an item on the item shape holds, in reading order: a strip's column by column."""
    if item["kind"] == KIND_CELL:
        return [item["cell"]]
    return [cell for column in item["columns"] for cell in column["cells"]]


def _sets_problem(sets: object) -> str:
    if not isinstance(sets, Mapping):
        return "sets is not a dict"
    for item_id, item in sets.items():
        said = item_id_problem(item_id)
        if said:
            return said
        said = item_problem(item)
        if said:
            return f"{said} (item {item_id})"
    return ""


def write_problem(write: object) -> str:
    """Why ``write`` is not one layout's items write, ``""`` when it is. Plain python, what :data:`WriteProblem` runs.

    ``{sets, deletes, order}``: ``sets`` item id to item, each id spelled
    right and each item on the item shape; ``deletes`` a list of ids;
    ``order`` a list of ids, or None for no order.
    """
    if not isinstance(write, Mapping):
        return "write is not a dict"
    said = keys_problem(write, {"sets", "deletes", "order"}, "write")
    if said:
        return said
    if not ids(write["deletes"]):
        return "write deletes is not a list of ids"
    if write["order"] is not None and not ids(write["order"]):
        return "write order is not a list of ids"
    return _sets_problem(write["sets"])


def _entries(held: object) -> Mapping:
    return held if isinstance(held, Mapping) else {}


def cells_problem(entries: object, cells: object, sets: object, deletes: object) -> str:
    """Why ``sets`` cannot land on a layout, by the cells they place, ``""`` when they can. Plain python.

    ``entries`` is the stored layout, ``cells`` the plane's cells. Every
    cell a set item holds is on the plane (a removed cell is not), and no
    cell sits in two items once ``deletes`` are gone and ``sets`` are in.
    Two stored items holding one cell, neither of them set, are not this
    write's doing and pass. Run on items checked on the shape already.
    """
    on_plane = set(listed(cells))
    written = _entries(sets)
    for item in written.values():
        for cell in item_cells(item):
            if cell not in on_plane:
                return f"cell {cell} is not on the plane"
    gone = set(listed(deletes))
    after = {k: v for k, v in _entries(entries).items() if k not in gone}
    after.update(written)
    holder: dict[str, str] = {}
    for item_id, item in after.items():
        if item_problem(item):
            continue
        for cell in item_cells(item):
            first = holder.setdefault(cell, item_id)
            if first != item_id and (first in written or item_id in written):
                return f"cell {cell} is in items {first} and {item_id}"
    return ""


def off_plane(item: object, cells: object) -> str:
    """Why ``item`` cannot land on a plane of ``cells``: a cell it holds not on it, ``""`` when none. Plain python."""
    on_plane = set(listed(cells))
    for cell in item_cells(item):  # type: ignore[arg-type]
        if cell not in on_plane:
            return f"cell {cell} is not on the plane"
    return ""


def column_problem(item: object, column: object) -> str:
    """Why a cell cannot go into column ``column`` of ``item``, ``""`` when it can. Plain python.

    ``item`` is a stored strip and ``column`` one of its columns' index.
    """
    if item_problem(item):
        return "item is not on the item shape"
    if item["kind"] != KIND_STRIP:  # type: ignore[index]
        return "item is not a strip"
    count = len(item["columns"])  # type: ignore[index]
    whole = isinstance(column, int) and not isinstance(column, bool)
    if not whole or not 0 <= column < count:  # type: ignore[operator]
        return f"column {column!r} is not one of the strip's {count}"
    return ""


# --- The fix-up --------------------------------------------------------------------------


def _shown(item: Mapping, on_plane: set[str], seen: set[str]) -> Mapping | None:
    """``item`` as drawn: its cells off the plane, or shown by an earlier item, left out. None for none left.

    Then the strip rules: an empty column goes, the shares left rescale to
    sum 1, a strip left with one cell reads as a cell item, an empty one goes.
    """
    if item["kind"] == KIND_CELL:
        cell = item["cell"]
        return item if cell in on_plane and cell not in seen else None
    columns = []
    for column in item["columns"]:
        kept = [c for c in column["cells"] if c in on_plane and c not in seen]
        if kept:
            columns.append({**column, "cells": kept})
    columns = rescaled(columns, len(item["columns"]))
    left = [c for column in columns for c in column["cells"]]
    if not left:
        return None
    if len(left) == 1:
        return {"kind": KIND_CELL, "cell": left[0]}
    return {**item, "columns": columns}


def _fill_id(cell: str, taken: set[str]) -> str:
    """The item id the fix-up gives ``cell``'s own item: drawn from the cell id, so a read and an op agree."""
    n = 0
    while True:
        digest = hashlib.sha256(f"{cell}/{n}".encode()).digest()
        item_id = "".join(ID_CHARS[b % len(ID_CHARS)] for b in digest[:6])
        if item_id not in taken:
            return item_id
        n += 1


def _arranged(entries: object, cells: object) -> list[tuple[str, Mapping | None, Mapping | None]]:
    """Every item of the fixed-up layout, in drawing order: ``(id, shown, added)``.

    A stored item is ``(id, shown, None)``, ``shown`` None when nothing of
    it is drawn (it stays stored). A cell on the plane in no item is
    ``(id, item, item)``, its own cell item, right after the item holding
    the cell before it in ``cells`` order, at the top when it is first. One
    pass over the items, one over the cells.
    """
    held = _entries(entries)
    on_plane = [c for c in dict.fromkeys(listed(cells)) if isinstance(c, str)]
    on_set = set(on_plane)
    seen: set[str] = set()
    holder: dict[str, str] = {}
    rows: list[tuple[str, Mapping | None, Mapping | None]] = []
    for item_id, item in held.items():
        shown = None if item_problem(item) else _shown(item, on_set, seen)
        if shown is not None:
            for cell in item_cells(shown):
                seen.add(cell)
                holder[cell] = item_id
        rows.append((item_id, shown, None))
    taken = set(held)
    after: dict[str | None, list] = {}
    for at, cell in enumerate(on_plane):
        if cell in seen:
            continue
        item_id = _fill_id(cell, taken)
        taken.add(item_id)
        item = {"kind": KIND_CELL, "cell": cell}
        anchor = holder[on_plane[at - 1]] if at else None
        after.setdefault(anchor, []).append((item_id, item, item))
        seen.add(cell)
        holder[cell] = item_id
    out: list[tuple[str, Mapping | None, Mapping | None]] = []
    stack = list(reversed(after.get(None, []) + rows))
    while stack:
        row = stack.pop()
        out.append(row)
        stack.extend(reversed(after.get(row[0], [])))
    return out


def layout_view(entries: object, cells: object) -> list[dict]:
    """The layout as it is drawn: ``[{id, kind, ...}]``, fixed up against the plane's cells. Plain python.

    ``entries`` is the stored layout (item id to item, in order), ``cells``
    the plane's cell ids in order. A cell no longer on the plane (removed or
    transferred out) is skipped, and so is a cell an earlier item shows;
    then the strip rules (:func:`_shown`). A cell on the plane in no item
    shows as its own cell item right after the item holding the cell
    before it in ``cells`` order (a strip counts as one item), at the top
    when nothing is before it. An entry off the item shape is skipped. An
    empty layout reads as one cell item per cell, in ``cells`` order.
    """
    return [{"id": i, **shown} for i, shown, _ in _arranged(entries, cells) if shown is not None]


#: ``LayoutView(entries, cells)``: :func:`layout_view`, what the pane ships.
LayoutView = nu.host(layout_view, name="LayoutView")


def fills(entries: object, cells: object) -> list[list]:
    """What :func:`layout_view` shows and the store lacks, as inserts: ``[[id, item, side, anchor]]``. Plain python.

    In order, each placed where the read draws it: ``side`` is ``"after"``
    the item drawn before it, ``"before"`` the first stored item when it
    comes first, ``"end"`` (anchor ``""``) on an empty store. Applied in
    order, the stored layout reads back as it did, with these ids.
    """
    out: list[list] = []
    rows = _arranged(entries, cells)
    first = next((i for i, _, added in rows if added is None), "")
    for at, (item_id, _, added) in enumerate(rows):
        if added is None:
            continue
        if at:
            out.append([item_id, added, "after", rows[at - 1][0]])
        elif first:
            out.append([item_id, added, "before", first])
        else:
            out.append([item_id, added, "end", ""])
    return out


# --- Moving one cell ---------------------------------------------------------------------


def _without(item: Mapping, cell: str) -> Mapping | None:
    """``item`` with ``cell`` taken out, by the strip rules. None when nothing is left."""
    if item["kind"] == KIND_CELL:
        return None if item["cell"] == cell else item
    columns = []
    for column in item["columns"]:
        kept = [c for c in column["cells"] if c != cell]
        if kept:
            columns.append({**column, "cells": kept})
    columns = rescaled(columns, len(item["columns"]))
    left = [c for column in columns for c in column["cells"]]
    if not left:
        return None
    if len(left) == 1:
        return {"kind": KIND_CELL, "cell": left[0]}
    return {**item, "columns": columns}


def taken_out(entries: object, cells: object, but: object = "") -> dict:
    """``{sets, deletes}`` taking ``cells`` out of every stored item holding one, but item ``but``. Plain python.

    A cell item of one goes. Out of a strip, by the strip rules: a column
    left empty goes, the shares left rescale, a strip left with one cell is
    a cell item in its place (same id), one left empty goes. Only what
    changes; an entry off the item shape is left alone.
    """
    out = set(listed(cells))
    sets: dict = {}
    deletes: list[str] = []
    for item_id, item in _entries(entries).items():
        if item_id == but or item_problem(item) or not out & set(item_cells(item)):
            continue
        kept: Mapping | None = item
        for cell in sorted(out):
            kept = _without(kept, cell) if kept is not None else None
        if kept is None:
            deletes.append(item_id)
        else:
            sets[item_id] = kept
    return {"sets": sets, "deletes": deletes}


def put_in(item: object, cell: object, column: object, index: object) -> object:
    """Strip ``item`` with ``cell`` in column ``column`` at ``index``. Plain python, what :data:`PutIn` runs.

    ``index`` is a place among the column's cells, past its end the end;
    the shares stay. The checks are :func:`column_problem`'s, made first.
    """
    columns = [dict(c) for c in item["columns"]]  # type: ignore[index]
    held = list(columns[column]["cells"])  # type: ignore[index]
    held.insert(min(int(index), len(held)), cell)  # type: ignore[call-overload]
    columns[column]["cells"] = held  # type: ignore[index]
    return {**item, "columns": columns}  # type: ignore[dict-item]


# --- One whole op ------------------------------------------------------------------------

#: The ops :func:`plan` works out.
OPS = ("add", "set", "remove", "move", "write", "place")


class _Rows:
    """A layout's items in order, changed in python, each change kept as the write that makes it.

    A write is ``[verb, id, value, anchor]``, verb one of ``set``, ``del``,
    ``before``, ``after`` (an insert next to ``anchor``). A move is a delete
    and an insert. Applied in order to the store, it reads as these rows.
    """

    def __init__(self, entries: Mapping) -> None:
        self.rows: list[list] = [[k, v] for k, v in entries.items()]
        self.writes: list[list] = []

    def ids(self) -> list[str]:
        return [r[0] for r in self.rows]

    def items(self) -> dict:
        return dict(self.rows)

    def has(self, item_id: object) -> bool:
        return item_id in self.ids()

    def known(self, item_id: object) -> None:
        if not self.has(item_id):
            raise Missing(f"no item {item_id}")

    def _at(self, item_id: str) -> int:
        return self.ids().index(item_id)

    def set(self, item_id: str, item: object) -> None:
        if self.has(item_id):
            self.rows[self._at(item_id)][1] = item
        else:
            self.rows.append([item_id, item])
        self.writes.append(["set", item_id, item, ""])

    def delete(self, item_id: str) -> None:
        del self.rows[self._at(item_id)]
        self.writes.append(["del", item_id, None, ""])

    def insert(self, item_id: str, item: object, side: str, anchor: str) -> None:
        at = self._at(anchor) + (side == "after")
        self.rows.insert(at, [item_id, item])
        self.writes.append([side, item_id, item, anchor])

    def move(self, item_id: str, side: str, anchor: str) -> None:
        item = self.rows[self._at(item_id)][1]
        self.delete(item_id)
        self.insert(item_id, item, side, anchor)

    def put(self, item_id: str, item: object, before: str, after: str) -> None:
        """A new item before or after a stored one, or last."""
        if before:
            self.known(before)
            self.insert(item_id, item, "before", before)
        elif after:
            self.known(after)
            self.insert(item_id, item, "after", after)
        else:
            self.set(item_id, item)

    def take_out(self, cells: list[str], but: str = "") -> None:
        changed = taken_out(self.items(), cells, but)
        for item_id in changed["deletes"]:
            self.delete(item_id)
        for item_id, item in changed["sets"].items():
            self.set(item_id, item)


def _anchors(args: Mapping) -> tuple[str, str]:
    before, after = args.get("before") or "", args.get("after") or ""
    if before and after:
        raise ValueError("placement takes before or after, not both")
    return before, after


def _new_id(rows: _Rows, given: object, cell: str) -> str:
    """The id given, checked, or one drawn from ``cell`` free in the layout, as the fill draws it.

    Never random: :func:`plan` runs as a query, so the same reads give the same writes.
    """
    if not given:
        return _fill_id(cell, set(rows.ids()))
    said = item_id_problem(given)
    if said:
        raise Refused(said)
    if rows.has(given):
        raise Exists(f"item {given} exists")
    return given  # type: ignore[return-value]


def _shaped(item: object) -> None:
    said = item_problem(item)
    if said:
        raise Refused(said)


def _on_plane(item: object, cells: object) -> None:
    said = off_plane(item, cells)
    if said:
        raise Refused(said)


def _add(rows: _Rows, cells: object, args: Mapping) -> None:
    item = args.get("item")
    given = args.get("id")
    if given and item_id_problem(given):
        raise Refused(item_id_problem(given))
    _shaped(item)
    item_id = _new_id(rows, given, item_cells(item)[0])  # type: ignore[arg-type]
    _on_plane(item, cells)
    before, after = _anchors(args)
    rows.put(item_id, item, before, after)
    rows.take_out(item_cells(item), item_id)  # type: ignore[arg-type]


def _set(rows: _Rows, cells: object, args: Mapping) -> None:
    item_id, item = args.get("id"), args.get("item")
    _shaped(item)
    rows.known(item_id)
    _on_plane(item, cells)
    rows.set(item_id, item)  # type: ignore[arg-type]
    rows.take_out(item_cells(item), item_id)  # type: ignore[arg-type]


def _remove(rows: _Rows, cells: object, args: Mapping) -> None:
    rows.known(args.get("id"))
    rows.delete(args["id"])


def _move(rows: _Rows, cells: object, args: Mapping) -> None:
    item_id = args.get("id")
    rows.known(item_id)
    before, after = _anchors(args)
    anchor = before or after
    if not anchor:
        last = rows.ids()[-1]
        if last != item_id:
            rows.move(item_id, "after", last)  # type: ignore[arg-type]
        return
    if anchor == item_id:
        raise Refused(f"item {item_id} cannot move next to itself")
    rows.known(anchor)
    rows.move(item_id, "before" if before else "after", anchor)  # type: ignore[arg-type]


def _write(rows: _Rows, cells: object, args: Mapping) -> None:
    write = {k: args.get(k) for k in ("sets", "deletes", "order")}
    said = write_problem(write) or cells_problem(
        rows.items(), cells, write["sets"], write["deletes"]
    )
    if said:
        raise Refused(said)
    for item_id in write["deletes"]:  # type: ignore[union-attr]
        if rows.has(item_id):
            rows.delete(item_id)
    for item_id, item in write["sets"].items():  # type: ignore[union-attr]
        rows.set(item_id, item)
    if write["order"] is not None:
        for item_id, side, anchor in order_moves(rows.ids(), write["order"]):
            rows.move(item_id, side, anchor)


def _place(rows: _Rows, cells: object, args: Mapping) -> None:
    cell = args.get("cell")
    if cell not in listed(cells):
        raise Refused(f"cell {cell} is not on plane {args.get('on')}")
    before, after = _anchors(args)
    into = args.get("into") or ""
    if into and (before or after):
        raise ValueError("place takes into or before / after, not both")
    if not into:
        item_id = _new_id(rows, args.get("new_id"), cell)  # type: ignore[arg-type]
        rows.put(item_id, {"kind": KIND_CELL, "cell": cell}, before, after)
        rows.take_out([cell], item_id)  # type: ignore[list-item]
        return
    if args.get("column") is None or args.get("index") is None:
        raise ValueError("place into a strip takes column and index")
    rows.take_out([cell])  # type: ignore[list-item]
    rows.known(into)
    held = rows.items()[into]
    said = column_problem(held, args.get("column"))
    if said:
        raise Refused(f"item {into}: {said}")
    rows.set(into, put_in(held, cell, args["column"], args.get("index") or 0))


_PLANNED = {
    "add": _add,
    "set": _set,
    "remove": _remove,
    "move": _move,
    "write": _write,
    "place": _place,
}


def _plane_live(plane: Mapping) -> None:
    """The plane is in the space, not removed, and on the web, as the reads in ``plane`` say."""
    name = plane.get("id")
    if not plane.get("known"):
        raise Missing(f"no plane {name}")
    if plane.get("removed"):
        raise Removed(f"plane {name} is removed")
    if not plane.get("on_web"):
        raise Missing(f"plane {name} is not on the web")


def plan(op: object, plane: object, entries: object, cells: object, args: object) -> list[list]:
    """One layout op worked out whole: the store writes it makes, in order. Plain python, what :data:`Plan` runs.

    ``op`` is one of :data:`OPS`. ``plane`` is ``{id, known, removed,
    on_web}``, the plane's row read; ``entries`` the stored layout,
    ``cells`` the plane's cells, ``args`` the op's arguments (anchors ``""``
    or None for none). The plane checked, then the fill (:func:`fills`),
    then the op's checks and change on the layout as the fill leaves it.
    The writes are :class:`_Rows`', the fill's first.

    Raises:
        Missing, Removed, Refused, Exists, ValueError: the op refuses, the
            error says why, and nothing is written.
    """
    _plane_live(plane if isinstance(plane, Mapping) else {})
    held = _entries(entries)
    rows = _Rows(held)
    for item_id, item, side, anchor in fills(held, cells):
        if side == "end":
            rows.set(item_id, item)
        else:
            rows.insert(item_id, item, side, anchor)
    _PLANNED[op](rows, cells, args if isinstance(args, Mapping) else {})  # type: ignore[index]
    return rows.writes


#: ``Plan(op, plane, entries, cells, args)``: :func:`plan`, every layout op's one host call. It
#: raises the op's refusal itself.
Plan = nu.host(plan, name="LayoutPlan")
