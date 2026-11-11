"""The web device's own nu interactions: small reads over plain values, kept out of the op and feed files.

- :data:`ErrorType`, :data:`ErrorMessage`: a caught error's type name and
  its message, what a toast says.
- :data:`Session`: the tab a plane run draws on, read off its env specs.
- :data:`Href`: a pane's URL, encoded the way the browser does.
- :data:`IconName`: a stored icon as a page link takes it.
- :data:`DeskIdProblem`, :data:`DeskProblem`: what is wrong with a desk id
  or a desk dict, ``""`` for nothing. :data:`ShapedDesk`,
  :data:`ShapedDesks`: stored desks with any not on the desk shape left out,
  in creation order. :data:`DeskPlanes`: every plane on those desks.
  :func:`pruned_desk`: a desk with the links to removed planes taken out.
  :data:`Favorites`: a new empty Favorites desk, its id minted.
- :class:`EventField`: one field off a browser event, strict.
- :class:`Drawing`: the term drawing one content item found at run time,
  landed under a ui ref (search hits).

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

import math
import re
import secrets
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING
from urllib.parse import quote

import nu
import nustd.ui
from nu.engine import Declared
from nu.lang import NULL, ScalarQuery
from nuspace.shapes.content import entries
from nuspace.specs.registry import content_spec
from nustd.ui.core import Ref as UiRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import StructuredRef
    from nu.lang.runtime import Runtime


__all__ = [
    "DESK_ID",
    "FAVORITES",
    "ITEM_ID",
    "KIND_PLANE",
    "KIND_STRIP",
    "SESSION_ENV",
    "DeskIdProblem",
    "DeskPlanes",
    "DeskProblem",
    "Drawing",
    "ErrorMessage",
    "ErrorType",
    "EventField",
    "Favorites",
    "Href",
    "IconName",
    "MovedOrder",
    "Session",
    "ShapedDesk",
    "ShapedDesks",
    "desk_planes",
    "desk_problem",
    "favorites",
    "mint_id",
    "moved_order",
    "ordered_desks",
    "pruned_desk",
    "shown_plane",
]


#: The name the session env factory is registered under, and the first item
#: of a run's env spec for a tab: ``["session", sid]``.
SESSION_ENV = "session"


def _exception(error: object) -> BaseException | None:
    """The live exception a ``TryCatch`` bound, when it bound one."""
    held = getattr(error, "exception", None)
    return held if isinstance(held, BaseException) else None


def _error_type(error: object) -> str:
    held = _exception(error)
    return type(held).__name__ if held is not None else "Error"


def _error_message(error: object) -> str:
    held = _exception(error)
    return str(held) if held is not None else str(error)


#: ``ErrorType(err)``: the class name of a caught error, ``Missing``, ``Refused``, ``KeyError``.
ErrorType = nu.host(_error_type, name="ErrorType")

#: ``ErrorMessage(err)``: a caught error's message, as ``str(exc)`` says it.
ErrorMessage = nu.host(_error_message, name="ErrorMessage")


def _session(envs: object) -> str:
    # A run's envs are the specs it was asked with, ``[["session", sid]]``
    # for a pane nav runs. "" for a run with no tab.
    for spec in envs if isinstance(envs, Sequence) else ():
        if isinstance(spec, Sequence) and len(spec) > 1 and spec[0] == SESSION_ENV:
            return str(spec[1])
    return ""


#: ``Session(envs)``: the tab id a plane run's env specs name, ``""`` for a run on no tab.
Session = nu.host(_session, name="Session")


def _href(plane: object, given: object) -> str:
    pairs = given if isinstance(given, Mapping) else {}
    search = nustd.ui.encode_query(dict(pairs))
    # encodeURIComponent's set, so a plane id reads the same on both sides.
    path = "/" + quote(str(plane), safe="!*'()")
    return f"{path}?{search}" if search else path


#: ``Href(plane, params)``: ``/<plane>``, or ``/<plane>?<params>``; a None param drops its key.
Href = nu.host(_href, name="Href")


def _icon_name(icon: object) -> str:
    # A stored icon is ``lucide:<name>`` or ``emoji:<char>``; a page link
    # takes the bare name or the character.
    text = "" if icon is None else str(icon)
    return text.partition(":")[2] if ":" in text else text


#: ``IconName(icon)``: a stored icon as a page link takes it, its prefix dropped.
IconName = nu.host(_icon_name, name="IconName")


# --- Desks -----------------------------------------------------------------------------
#
# A desk is ``{name, items}``. An item is a plane item or a strip, each with
# an ``id``. A plane item and a strip's pane each hold ``original`` (the link
# it was saved with) and, when navigated away, ``recent`` (the link it shows
# now). A link is ``{plane, params}``. The plain python checks and the plain
# python pruning live here; the ops and the pruner run them through hosts.

#: A desk id: 8 chars ``[a-z0-9]``, minted by the browser.
DESK_ID = re.compile(r"[a-z0-9]{8}")

#: An item id: 6 chars ``[a-z0-9]``, minted by the browser, unique within its desk.
ITEM_ID = re.compile(r"[a-z0-9]{6}")

#: The id chars, what :func:`mint_desk` draws from.
_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"

#: The two kinds of item.
KIND_PLANE = "plane"
KIND_STRIP = "strip"

#: The name of the desk seeded once per space (:func:`mint_desk`).
FAVORITES = "Favorites"

#: How far a column's shares may be off 1, for floats the browser added up.
_SHARE_SLACK = 1e-3


def _desk_id_problem(desk_id: object) -> str:
    if isinstance(desk_id, str) and DESK_ID.fullmatch(desk_id):
        return ""
    return f"desk id {desk_id!r} is not 8 chars of a-z and 0-9"


#: ``DeskIdProblem(id)``: why a desk id is spelled wrong, ``""`` when it is right.
DeskIdProblem = nu.host(_desk_id_problem, name="DeskIdProblem")


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


def _item_problem(item: object, at: str) -> str:
    if not isinstance(item, Mapping):
        return f"{at} is not a dict"
    kind = item.get("kind")
    if kind == KIND_PLANE:
        said = _keys(item, {"id", "kind", "original"}, at, optional=_RECENT)
    elif kind == KIND_STRIP:
        said = _keys(item, {"id", "kind", "columns"}, at)
    else:
        return f"{at} kind is not {KIND_PLANE!r} or {KIND_STRIP!r}"
    if said:
        return said
    item_id = item["id"]
    if not isinstance(item_id, str) or not ITEM_ID.fullmatch(item_id):
        return f"{at} id {item_id!r} is not 6 chars of a-z and 0-9"
    return _links_problem(item, at) if kind == KIND_PLANE else _strip_problem(item, at)


def desk_problem(desk: object) -> str:
    """Why ``desk`` is not a desk, ``""`` when it is. Plain python, what :data:`DeskProblem` runs.

    A desk is ``{name, items}``: ``name`` a string, ``items`` a list, empty
    or not. An item is a plane item ``{id, kind: "plane", original,
    recent?}`` or a strip ``{id, kind: "strip", columns}``, its id 6 chars
    of a-z and 0-9 and unique in the desk. A strip has columns ``{width?,
    panes}``, each with panes ``{share, original, recent?}``. A link
    (``original``, ``recent``) is ``{plane, params}``, ``params`` str to
    str. A width is a positive number of px (none: the default width),
    shares are numbers in ``(0, 1]``, a column's shares sum
    to 1, a column is never empty, a strip holds two panes or more, and a
    strip never shows one plane twice (what a pane shows: its recent, else its original). The
    same plane may sit in any number of items. No plane is looked up.
    """
    said = _keys(desk, {"name", "items"}, "desk")
    if said:
        return said
    items = desk["items"]  # type: ignore[index]
    if not isinstance(desk["name"], str):  # type: ignore[index]
        return "desk name is not a string"
    if not isinstance(items, list):
        return "desk items is not a list"
    for i, item in enumerate(items):
        said = _item_problem(item, f"item {i}")
        if said:
            return said
    ids = [item["id"] for item in items]
    twice = sorted({i for i in ids if ids.count(i) > 1})
    return f"item id {twice[0]} is twice in the desk" if twice else ""


#: ``DeskProblem(desk)``: why a desk dict is not the desk shape, ``""`` when it is
#: (:func:`desk_problem`). The shape the browser's ``Desk`` type mirrors.
DeskProblem = nu.host(desk_problem, name="DeskProblem")


def _shaped_desk(desk: object) -> object:
    return NULL if desk_problem(desk) else desk


def _listed(held: object) -> list:
    return list(held) if isinstance(held, Sequence) and not isinstance(held, str) else []


def ordered_desks(desks: object, order: object) -> dict:
    """``{desk_id: desk}`` of the desks on the desk shape, in creation order. Plain python.

    ``order`` is ``Web.desk_order``, the ids as they were created. A desk
    it lacks (one a program stored straight) comes after, by id. A desk not
    on the desk shape (one stored in an older shape) is left out: dropped
    on read, never migrated.
    """
    if not isinstance(desks, Mapping):
        return {}
    listed = [d for d in dict.fromkeys(_listed(order)) if d in desks]
    rest = sorted(d for d in desks if d not in listed)
    return {d: desks[d] for d in [*listed, *rest] if not desk_problem(desks[d])}


#: ``ShapedDesk(desk)``: the desk as it is when it has the desk shape, NULL when not.
ShapedDesk = nu.host(_shaped_desk, name="ShapedDesk")

#: ``ShapedDesks(desks, order)``: :func:`ordered_desks`, the desks shipped and listed.
ShapedDesks = nu.host(ordered_desks, name="ShapedDesks")


def moved_order(order: object, desk_id: str, before: str) -> list[str]:
    """``order`` with ``desk_id`` moved in front of ``before``, last when ``before`` is ``""`` or not there. Plain python.

    ``desk_id`` is placed even when ``order`` lacks it (a desk a program
    stored straight), and appears once.
    """
    ids = [d for d in dict.fromkeys(_listed(order)) if d != desk_id]
    at = ids.index(before) if before in ids else len(ids)
    ids.insert(at, desk_id)
    return ids


#: ``MovedOrder(order, desk_id, before)``: :func:`moved_order`, the creation order after a move.
MovedOrder = nu.host(moved_order, name="MovedOrder")


def desk_planes(desks: object) -> list[str]:
    """Every plane id a desk of ``{desk_id: desk}`` holds, original or recent, once each, sorted.

    A desk not on the desk shape is skipped. Plain python.
    """
    if not isinstance(desks, Mapping):
        return []
    found: set[str] = set()
    for desk in desks.values():
        if desk_problem(desk):
            continue
        for item in desk["items"]:
            held = [item] if item["kind"] == KIND_PLANE else _panes(item)
            for h in held:
                found.add(h["original"]["plane"])
                if "recent" in h:
                    found.add(h["recent"]["plane"])
    return sorted(found)


#: ``DeskPlanes(desks)``: :func:`desk_planes`, every plane on a desk, original or recent.
DeskPlanes = nu.host(desk_planes, name="DeskPlanes")


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
    place, its id kept, with that pane's links.
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
        return {"id": strip["id"], "kind": KIND_PLANE, **links}
    return {**strip, "columns": columns}


def pruned_desk(desk: Mapping, removed: object) -> Mapping:
    """``desk`` with every link to a ``removed`` plane taken out. Plain python, what the pruner runs.

    A plane item or a pane whose original is removed comes out; a recent on
    a removed plane is dropped (the item shows its original again). Then the
    strip rules: a column left empty goes, a strip left with one pane is a
    plane item in its place, a strip left empty goes. The desk itself
    stays, empty or not. The same dict comes back when nothing changed.
    """
    gone = set(_listed(removed))
    items = []
    for item in desk["items"]:
        if item["kind"] == KIND_PLANE:
            kept = _unlinked(item, gone)
        else:
            kept = _pruned_strip(item, gone)
        if kept is not None:
            items.append(kept)
    return desk if items == desk["items"] else {**desk, "items": items}


def mint_id(size: int) -> str:
    """A fresh id of ``size`` chars of a-z and 0-9, as the browser mints desk and item ids."""
    return "".join(secrets.choice(_ID_CHARS) for _ in range(size))


def favorites() -> dict:
    """``{id, desk}``: a new, empty Favorites desk, its id (8 chars) minted here. Plain python, what :data:`Favorites` runs."""
    return {"id": mint_id(8), "desk": {"name": FAVORITES, "items": []}}


#: ``Favorites()``: :func:`favorites`, a new empty Favorites desk, its id minted.
Favorites = nu.host(favorites, name="Favorites")


# --- Events ----------------------------------------------------------------------------


def _ids(held: object) -> bool:
    return isinstance(held, list) and all(isinstance(i, str) for i in held)


#: What :class:`EventField` checks a field against: a test and what it says.
_KINDS: dict[str, tuple[Callable[[object], bool], str]] = {
    "str": (lambda v: isinstance(v, str), "a string"),
    "bool": (lambda v: isinstance(v, bool), "a bool"),
    "dict": (lambda v: isinstance(v, dict), "a dict"),
    "ids": (_ids, "a list of ids"),
    # An anchor may be left out: it reads "", the end.
    "anchor": (lambda v: v is None or isinstance(v, str), "an id"),
}


class EventField(ScalarQuery):
    """One field off a browser event, strict: present and of the kind asked, or a raise.

    A malformed event never runs an op on a guess: its guard toasts the
    raise like any other failure.

    Args:
        row: The event.
        field: The field's name.
        kind: ``"str"``, ``"bool"``, ``"dict"``, ``"ids"`` (a list of
            strings) or ``"anchor"`` (a string, or absent for ``""``).

    Raises:
        ValueError: The field is absent or of another kind. At build, a
            kind none of these.
    """

    def __init__(self, row: nu.Nu, field: str, kind: str) -> None:
        if kind not in _KINDS:
            msg = f"EventField kind {kind!r} is none of {sorted(_KINDS)}"
            raise ValueError(msg)
        super().__init__(row)
        self._payload["field"] = field
        self._payload["kind"] = kind

    def _read(self, row: object) -> object:
        field, kind = self._payload["field"], self._payload["kind"]
        test, what = _KINDS[kind]
        held = row.get(field) if isinstance(row, Mapping) else None
        if not test(held):
            msg = f"malformed event: {field!r} must be {what}, got {held!r}"
            raise ValueError(msg)
        if kind == "anchor":
            return held or ""
        return list(held) if isinstance(held, list) else held

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (row,) = children

        def thunk(rt: Runtime) -> object:
            return self._read(row(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (row,) = children

        async def athunk(rt: Runtime) -> object:
            return self._read(await row(rt))

        return athunk


# --- Drawing -----------------------------------------------------------------------


def _drawn_ui(ref: StructuredRef) -> bool:
    """A ``rooted`` predicate: every chain but a bare ui one stays where it is."""
    return not isinstance(ref, UiRef)


class Drawing(ScalarQuery):
    """The term drawing one item by its address, landed under ``under``. Run it with ``nu.Eval``.

    For a program that learns which item to draw only at run time (eg a
    search hit): the kind is found by name (``content_spec``), the item
    reached through :func:`entries`, and its :meth:`~Content.render` (or
    :meth:`~Content.render_hit`) term built, its bare ui chains spliced
    under ``under``. ``under`` is a ref the program names bare like any of
    its ui refs: it sits in a structural slot, never read, so the program's
    own rewrites land it first and the drawing lands where it does.

    Args:
        kind: The kind's registered name.
        level: The scope's level, one of :data:`LEVELS`.
        scope: The cell or plane id, ``""`` for the space.
        key: The item's content key.
        under: A ui ref the drawing lands under.
        hit: Draw ``render_hit`` rather than ``render``.

    Yields:
        The drawing, a term: ``nu.Eval(Drawing(...))`` draws it. It reads the
        item bare, so its caller brackets it. ``atomic`` cannot see the reads
        of a term built at run time, so the bracket names its store:
        ``nustd.kv.Snapshot(nu.Eval(Drawing(...)), scope=nuspace.State)``.
    """

    _structural = Declared(value=frozenset({4}), name="structural")

    def __init__(
        self,
        kind: nu.StrArg,
        level: nu.StrArg,
        scope: nu.StrArg,
        key: nu.StrArg,
        under: nu.Nu,
        *,
        hit: bool = False,
    ) -> None:
        super().__init__(kind, level, scope, key, under)
        self._payload["hit"] = hit

    def _term(self, kind: object, level: object, scope: object, key: object) -> nu.Nu:
        found = content_spec(str(kind)).kind
        item = entries(found, str(level), str(scope))[str(key)]
        drawn = found.render_hit(item) if self._payload["hit"] else found.render(item)
        return nu.shape.reroot(drawn, self._children[4], rooted=_drawn_ui)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, level, scope, key = children[:4]

        def thunk(rt: Runtime) -> object:
            return self._term(kind(rt), level(rt), scope(rt), key(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, level, scope, key = children[:4]

        async def athunk(rt: Runtime) -> object:
            return self._term(await kind(rt), await level(rt), await scope(rt), await key(rt))

        return athunk
