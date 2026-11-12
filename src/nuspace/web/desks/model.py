"""The desk shape in plain python, and the hosts the desk ops, the feed and the pruner run it through.

- Checks: :data:`DeskIdProblem`, :data:`ItemIdProblem`, :data:`ItemProblem`
  (one stored item), :data:`WriteProblem` (one desk's items write), each
  ``""`` for nothing wrong.
- Reads: :data:`DeskView`, :data:`DesksView` (a stored desk as it is read,
  ``{name, items}``), :data:`DeskPlanes` (every plane on the desks).
- Placing: :data:`OrderMoves` (the moves putting items in an order),
  :data:`Items` (a desk's items list as entries), :data:`NewId`.
- Changing items: :data:`SavedEntries`, :data:`ResetItem`,
  :data:`PrunedEntries`.

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

import math
import re
import secrets
from collections.abc import Mapping, Sequence

import nu


__all__ = [
    "DESK_ID",
    "FAVORITES",
    "ITEM_ID",
    "KIND_PLANE",
    "KIND_STRIP",
    "DeskIdProblem",
    "DeskPlanes",
    "DeskView",
    "DesksView",
    "ItemIdProblem",
    "ItemProblem",
    "Items",
    "NewId",
    "OrderMoves",
    "PrunedEntries",
    "ResetItem",
    "SavedEntries",
    "WriteProblem",
    "desk_planes",
    "desk_view",
    "desks_view",
    "item_problem",
    "items_of",
    "mint_id",
    "order_moves",
    "pruned_entries",
    "pruned_item",
    "reset_item",
    "saved_entries",
    "shown_plane",
    "write_problem",
]


# A desk is stored as :class:`~nuspace.web.shapes.Desk`: a name and its entries,
# item id to item, in desk order. An item is a plane item or a strip, its id
# the key, never in the value. A plane item and a strip's pane each hold
# ``original`` (the link it was saved with) and, when navigated away,
# ``recent`` (the link it shows now). A link is ``{plane, params}``. Read
# back, a desk is ``{name, items}``: its items in order, each with its ``id``,
# the shape the browser's ``Desk`` has.

#: A desk id: 8 chars ``[a-z0-9]``, minted by the browser.
DESK_ID = re.compile(r"[a-z0-9]{8}")

#: An item id: 6 chars ``[a-z0-9]``, minted by the browser, unique within its desk.
ITEM_ID = re.compile(r"[a-z0-9]{6}")

#: The id chars, what :func:`mint_id` draws from.
_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

#: The two kinds of item.
KIND_PLANE = "plane"
KIND_STRIP = "strip"

#: The name of the desk seeded once per space.
FAVORITES = "Favorites"

#: How far a column's shares may be off 1, for floats the browser added up.
_SHARE_SLACK = 1e-3


def _desk_id_problem(desk_id: object) -> str:
    if isinstance(desk_id, str) and DESK_ID.fullmatch(desk_id):
        return ""
    return f"desk id {desk_id!r} is not 8 chars of a-z and 0-9"


def _item_id_problem(item_id: object) -> str:
    if isinstance(item_id, str) and ITEM_ID.fullmatch(item_id):
        return ""
    return f"item id {item_id!r} is not 6 chars of a-z and 0-9"


#: ``DeskIdProblem(id)``: why a desk id is spelled wrong, ``""`` when it is right.
DeskIdProblem = nu.host(_desk_id_problem, name="DeskIdProblem")

#: ``ItemIdProblem(id)``: why an item id is spelled wrong, ``""`` when it is right.
ItemIdProblem = nu.host(_item_id_problem, name="ItemIdProblem")


def _fraction(value: object) -> bool:
    """A number in ``(0, 1]``, never a bool."""
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return number and math.isfinite(value) and 0 < value <= 1  # type: ignore[operator]


def _px(value: object) -> bool:
    """A positive finite number, never a bool."""
    number = isinstance(value, (int, float)) and not isinstance(value, bool)
    return number and math.isfinite(value) and value > 0  # type: ignore[operator]


#: What a column may hold beside its panes: its width, px.
_WIDTH = frozenset({"width"})


def _keys(
    held: object, keys: set[str], what: str, *, optional: frozenset[str] = frozenset()
) -> str:
    """Why ``held`` is not a dict of ``keys``, plus any of ``optional``, ``""`` when it is."""
    if not isinstance(held, Mapping):
        return f"{what} is not a dict"
    if not keys <= set(held) <= keys | optional:
        return f"{what} has keys {sorted(held)}, wants {sorted(keys)}"
    return ""


def _link_problem(link: object, at: str) -> str:
    said = _keys(link, {"plane", "params"}, at)
    if said:
        return said
    plane, params = link["plane"], link["params"]  # type: ignore[index]
    if not isinstance(plane, str) or not plane:
        return f"{at} plane is not a plane id"
    pairs = isinstance(params, Mapping) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in params.items()
    )
    return "" if pairs else f"{at} params is not str to str"


#: What a plane item or a pane may hold beside its own keys.
_RECENT = frozenset({"recent"})


def _links_problem(held: Mapping, at: str) -> str:
    """Why the ``original`` or the ``recent`` of a plane item or a pane is not a link."""
    said = _link_problem(held["original"], f"{at} original")
    if said or "recent" not in held:
        return said
    return _link_problem(held["recent"], f"{at} recent")


def shown_plane(held: Mapping) -> str:
    """The plane a plane item or a pane shows: its recent's when it has one, else its original's."""
    return held.get("recent", held["original"])["plane"]


def _pane_problem(pane: object, at: str) -> str:
    said = _keys(pane, {"share", "original"}, at, optional=_RECENT)
    if said:
        return said
    if not _fraction(pane["share"]):  # type: ignore[index]
        return f"{at} share is not a number in (0, 1]"
    return _links_problem(pane, at)  # type: ignore[arg-type]


def _column_problem(column: object, at: str) -> str:
    said = _keys(column, {"panes"}, at, optional=_WIDTH)
    if said:
        return said
    panes = column["panes"]  # type: ignore[index]
    if "width" in column and not _px(column["width"]):  # type: ignore[operator, index]
        return f"{at} width is not a positive number of px"
    if not isinstance(panes, list) or not panes:
        return f"{at} has no panes"
    for i, pane in enumerate(panes):
        said = _pane_problem(pane, f"{at} pane {i}")
        if said:
            return said
    if abs(sum(p["share"] for p in panes) - 1) > _SHARE_SLACK:
        return f"{at} shares do not sum to 1"
    return ""


def _strip_problem(strip: Mapping, at: str) -> str:
    columns = strip["columns"]
    if not isinstance(columns, list) or not columns:
        return f"{at} has no columns"
    for c, column in enumerate(columns):
        said = _column_problem(column, f"{at} column {c}")
        if said:
            return said
    shown = [shown_plane(p) for c in columns for p in c["panes"]]
    if len(shown) < 2:
        return f"{at} has one pane, a plane item then"
    twice = sorted({p for p in shown if shown.count(p) > 1})
    return f"{at} shows plane {twice[0]} twice" if twice else ""


def item_problem(item: object) -> str:
    """Why ``item`` is not a stored item, ``""`` when it is. Plain python, what :data:`ItemProblem` runs.

    A plane item ``{kind: "plane", original, recent?}`` or a strip ``{kind:
    "strip", columns}``, no id (the id is its key). A strip has columns
    ``{width?, panes}``, each with panes ``{share, original, recent?}``. A
    link (``original``, ``recent``) is ``{plane, params}``, ``params`` str
    to str. A width is a positive number of px (none: the default width),
    shares are numbers in ``(0, 1]``, a column's shares sum to 1, a column
    is never empty, a strip holds two panes or more, and a strip never shows
    one plane twice (what a pane shows: its recent, else its original). The
    same plane may sit in any number of items. No plane is looked up.
    """
    if not isinstance(item, Mapping):
        return "item is not a dict"
    kind = item.get("kind")
    if kind == KIND_PLANE:
        said = _keys(item, {"kind", "original"}, "item", optional=_RECENT)
    elif kind == KIND_STRIP:
        said = _keys(item, {"kind", "columns"}, "item")
    else:
        return f"item kind is not {KIND_PLANE!r} or {KIND_STRIP!r}"
    if said:
        return said
    return _links_problem(item, "item") if kind == KIND_PLANE else _strip_problem(item, "strip")


#: ``ItemProblem(item)``: why an item is not the stored item shape, ``""`` when it is (:func:`item_problem`).
ItemProblem = nu.host(item_problem, name="ItemProblem")


def _listed(held: object) -> list:
    return list(held) if isinstance(held, Sequence) and not isinstance(held, str) else []


def _ids(held: object) -> bool:
    return isinstance(held, list) and all(isinstance(i, str) for i in held)


def write_problem(write: object) -> str:
    """Why ``write`` is not one desk's items write, ``""`` when it is. Plain python, what :data:`WriteProblem` runs.

    ``{desk_id, sets, deletes, order?}``: ``sets`` item id to item, each
    id spelled right and each item on the item shape; ``deletes`` and
    ``order`` lists of ids. A ``sets`` alone (no ``desk_id``) is checked the
    same, the way :func:`~.ops.write_items` takes it.
    """
    if not isinstance(write, Mapping):
        return "write is not a dict"
    said = _keys(write, {"desk_id", "sets", "deletes"}, "write", optional=frozenset({"order"}))
    if said:
        return said
    if not isinstance(write["desk_id"], str):
        return "write desk_id is not a string"
    if not _ids(write["deletes"]):
        return "write deletes is not a list of ids"
    if "order" in write and write["order"] is not None and not _ids(write["order"]):
        return "write order is not a list of ids"
    return _sets_problem(write["sets"])


def _sets_problem(sets: object) -> str:
    if not isinstance(sets, Mapping):
        return "sets is not a dict"
    for item_id, item in sets.items():
        said = _item_id_problem(item_id) or item_problem(item)
        if said:
            return f"{said} (item {item_id})" if not said.startswith("item id") else said
    return ""


#: ``WriteProblem(write)``: why a write is not one desk's items write, ``""`` when it is (:func:`write_problem`).
WriteProblem = nu.host(write_problem, name="WriteProblem")


def items_of(items: object) -> dict:
    """``{item_id: item}`` from a desk's ``items`` list, each item without its id. Plain python, what :data:`Items` runs.

    What turns the browser's ``Desk`` back into entries. Anything not a list
    of dicts with an ``id`` gives what it can, and the write's check
    refuses the rest.
    """
    out: dict = {}
    for held in _listed(items):
        if isinstance(held, Mapping) and "id" in held:
            out[held["id"]] = {k: v for k, v in held.items() if k != "id"}
    return out


#: ``Items(items)``: :func:`items_of`, a desk's items list as entries.
Items = nu.host(items_of, name="Items")


# --- Reads ------------------------------------------------------------------------------


def desk_view(desk: object) -> object:
    """A stored desk as it is read: ``{name, items}``, its items in order, each with its ``id``. Plain python.

    An entry off the item shape (one a program wrote straight) is left out.
    """
    if not isinstance(desk, Mapping):
        return None
    entries = desk.get("entries")
    held = entries if isinstance(entries, Mapping) else {}
    items = [{"id": i, **item} for i, item in held.items() if not item_problem(item)]
    name = desk.get("name")
    return {"name": name if isinstance(name, str) else "", "items": items}


def desks_view(desks: object) -> dict:
    """``{desk_id: desk}`` of every stored desk as it is read (:func:`desk_view`), in sidebar order. Plain python."""
    if not isinstance(desks, Mapping):
        return {}
    return {d: desk_view(desk) for d, desk in desks.items() if isinstance(desk, Mapping)}


#: ``DeskView(desk)``: :func:`desk_view`.
DeskView = nu.host(desk_view, name="DeskView")

#: ``DesksView(desks)``: :func:`desks_view`, what ships and lists.
DesksView = nu.host(desks_view, name="DesksView")


def _entries(desk: object) -> Mapping:
    entries = desk.get("entries") if isinstance(desk, Mapping) else None
    return entries if isinstance(entries, Mapping) else {}


def _links(item: Mapping) -> list[Mapping]:
    """The plane item itself, or every pane of a strip: what holds links."""
    return [item] if item["kind"] == KIND_PLANE else _panes(item)


def desk_planes(desks: object) -> list[str]:
    """Every plane id a stored desk of ``{desk_id: desk}`` holds, original or recent, once each, sorted.

    An entry off the item shape is skipped. Plain python.
    """
    if not isinstance(desks, Mapping):
        return []
    found: set[str] = set()
    for desk in desks.values():
        for item in _entries(desk).values():
            if item_problem(item):
                continue
            for h in _links(item):
                found.add(h["original"]["plane"])
                if "recent" in h:
                    found.add(h["recent"]["plane"])
    return sorted(found)


#: ``DeskPlanes(desks)``: :func:`desk_planes`, every plane on a desk, original or recent.
DeskPlanes = nu.host(desk_planes, name="DeskPlanes")


# --- Placing ------------------------------------------------------------------------------


def order_moves(current: object, order: object) -> list[list[str]]:
    """The moves putting ``current`` (item ids, in order) into ``order``: ``[[id, "before" | "after", anchor]]``. Plain python.

    The ids of ``order`` that are in ``current`` come first, in that order;
    the rest keep their order after them. An id ``order`` names that is not
    there, or names twice, is skipped. Only the moves that change something
    are given, each one an ``OrderedDictRef.move``.
    """
    now = list(dict.fromkeys(_listed(current)))
    wanted = [i for i in dict.fromkeys(_listed(order)) if i in now]
    moves: list[list[str]] = []
    for at, item_id in enumerate(wanted):
        if now.index(item_id) == at:
            continue
        now.remove(item_id)
        if at == 0:
            moves.append([item_id, "before", now[0]])
        else:
            moves.append([item_id, "after", wanted[at - 1]])
        now.insert(at, item_id)
    return moves


#: ``OrderMoves(current, order)``: :func:`order_moves`.
OrderMoves = nu.host(order_moves, name="OrderMoves")


def mint_id(size: int) -> str:
    """A fresh id of ``size`` chars of a-z and 0-9, as the browser mints desk and item ids."""
    return "".join(secrets.choice(_ID_CHARS) for _ in range(size))


#: ``NewId(size)``: :func:`mint_id`, 8 for a desk, 6 for an item. Free checks are the caller's.
NewId = nu.host(mint_id, name="NewId")


# --- Save, reset, prune --------------------------------------------------------------------


def _panes(strip: Mapping) -> list[Mapping]:
    return [p for c in strip["columns"] for p in c["panes"]]


def _unlinked(held: Mapping, gone: set[str]) -> Mapping | None:
    """A plane item or pane with no link to a ``gone`` plane: None when its original is gone.

    A recent on a gone plane is dropped, so it shows its original again.
    """
    if held["original"]["plane"] in gone:
        return None
    if "recent" in held and held["recent"]["plane"] in gone:
        return {k: v for k, v in held.items() if k != "recent"}
    return held


def _pruned_strip(strip: Mapping, gone: set[str]) -> Mapping | None:
    """A strip with ``gone`` planes taken out, None when no pane is left.

    A pane that, its recent dropped, shows a plane an earlier pane of the
    strip shows goes too: a strip never shows one plane twice. A column
    left empty goes, the shares left in a column are scaled back to sum 1
    (widths stay). A strip left with one pane becomes a plane item in its
    place (the caller keeps its id), with that pane's links.
    """
    columns = []
    seen: set[str] = set()
    for column in strip["columns"]:
        panes = []
        for pane in column["panes"]:
            kept = _unlinked(pane, gone)
            if kept is None or shown_plane(kept) in seen:
                continue
            seen.add(shown_plane(kept))
            panes.append(kept)
        if not panes:
            continue
        if len(panes) < len(column["panes"]):
            total = sum(p["share"] for p in panes)
            panes = [{**p, "share": p["share"] / total} for p in panes]
        columns.append({**column, "panes": panes})
    left = [p for c in columns for p in c["panes"]]
    if not left:
        return None
    if len(left) == 1:
        (pane,) = left
        links = {k: pane[k] for k in ("original", "recent") if k in pane}
        return {"kind": KIND_PLANE, **links}
    return {**strip, "columns": columns}


def pruned_item(item: Mapping, removed: object) -> Mapping | None:
    """``item`` with every link to a ``removed`` plane taken out, None when nothing is left. Plain python.

    A plane item or a pane whose original is removed comes out; a recent on
    a removed plane is dropped (it shows its original again). Then the strip
    rules: a column left empty goes, a strip left with one pane is a plane
    item, a strip left empty goes.
    """
    gone = set(_listed(removed))
    if item["kind"] == KIND_PLANE:
        return _unlinked(item, gone)
    return _pruned_strip(item, gone)


def pruned_entries(desk: object, removed: object) -> dict:
    """``{sets, deletes}`` taking ``removed`` planes off one stored desk. Plain python, what :data:`PrunedEntries` runs.

    Only what changes: an item pruned (:func:`pruned_item`) is in ``sets``,
    one left empty in ``deletes``. An entry off the item shape is left
    alone. The desk itself always stays.
    """
    sets: dict = {}
    deletes: list[str] = []
    for item_id, item in _entries(desk).items():
        if item_problem(item):
            continue
        kept = pruned_item(item, removed)
        if kept is None:
            deletes.append(item_id)
        elif kept != item:
            sets[item_id] = kept
    return {"sets": sets, "deletes": deletes}


#: ``PrunedEntries(desk, removed)``: :func:`pruned_entries`.
PrunedEntries = nu.host(pruned_entries, name="PrunedEntries")


def _saved(held: Mapping) -> Mapping:
    if "recent" not in held:
        return held
    return {**{k: v for k, v in held.items() if k != "recent"}, "original": held["recent"]}


def saved_entries(desk: object) -> dict:
    """``{item_id: item}`` of every item of a stored desk with a recent, each recent made its original. Plain python.

    What save writes: an item with no recent anywhere is left out.
    """
    out: dict = {}
    for item_id, item in _entries(desk).items():
        if item_problem(item):
            continue
        if item["kind"] == KIND_PLANE:
            saved = _saved(item)
        else:
            columns = [{**c, "panes": [_saved(p) for p in c["panes"]]} for c in item["columns"]]
            saved = {**item, "columns": columns}
        if saved != item:
            out[item_id] = saved
    return out


#: ``SavedEntries(desk)``: :func:`saved_entries`, what :func:`~.ops.save_desk` writes.
SavedEntries = nu.host(saved_entries, name="SavedEntries")


def reset_item(item: object) -> object:
    """``item`` with every recent dropped: it shows its originals. Plain python, what :data:`ResetItem` runs.

    A strip whose panes then show one plane twice keeps the first and drops
    the later ones, as pruning does, so it may come back a plane item.
    """
    if not isinstance(item, Mapping) or item_problem(item):
        return item
    if item["kind"] == KIND_PLANE:
        return {k: v for k, v in item.items() if k != "recent"}
    columns = [
        {**c, "panes": [{k: v for k, v in p.items() if k != "recent"} for p in c["panes"]]}
        for c in item["columns"]
    ]
    return _pruned_strip({**item, "columns": columns}, set())


#: ``ResetItem(item)``: :func:`reset_item`.
ResetItem = nu.host(reset_item, name="ResetItem")
