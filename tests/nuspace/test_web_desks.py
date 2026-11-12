"""``nuspace.web.desks``: the desk and item ops, the desk model, the role planes' seeding, and the desks feed.

Every op is a bare term, run here inside ``nuspace.atomic`` as a caller
would. The feed runs in one tab over a fake session, as ``test_web.py``.
"""

from __future__ import annotations

import asyncio
import copy

import pytest

import nu
import nuspace
import nuspace.web as web
from nu.lang import is_null
from nuspace.errors import Exists, Missing, Refused
from nuspace.ops.plane import DEFAULT_ICON
from nuspace.shapes import Space
from nuspace.specs import space_registry
from nuspace.web.desks.model import (
    DESK_ID,
    desk_view,
    item_problem,
    items_of,
    order_moves,
    reset_item,
    saved_entries,
    write_problem,
)
from nuspace.web.planes import ensure
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

D = web.desks


def link(plane: str, **params: str) -> dict:
    return {"plane": plane, "params": params}


#: A plane item navigated away: original p1, recent p4.
PLANE = {"kind": "plane", "original": link("p1"), "recent": link("p4", run="43")}

#: A strip of two columns: one of two panes, then one of p1 again (a plane may
#: sit in several items).
STRIP = {
    "kind": "strip",
    "columns": [
        {
            "width": 600,
            "panes": [
                {"share": 0.6, "original": link("p2", k="v")},
                {"share": 0.4, "original": link("p3")},
            ],
        },
        {"panes": [{"share": 1, "original": link("p1")}]},
    ],
}

#: The two as a desk reads back, and as the browser sends one.
DESK = {
    "name": "Train run 42 + Logs",
    "items": [{"id": "k3x9ab", **PLANE}, {"id": "q7m2zz", **STRIP}],
}


def plain(plane: str, recent: str | None = None) -> dict:
    """A plane item on ``plane``, navigated to ``recent`` when given."""
    item = {"kind": "plane", "original": link(plane)}
    if recent:
        item["recent"] = link(recent)
    return item


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def read(store, desk_id: str) -> dict:
    return await store.read(D.get_desk(desk_id))


async def ids(store, desk_id: str) -> list[str]:
    return [i["id"] for i in (await read(store, desk_id))["items"]]


async def made(store, desk_id: str = "abcd1234", desk: dict = DESK) -> None:
    """A desk stored as the browser's create would: the desk, then its items."""
    await do(store, D.create_desk(desk["name"], id=desk_id))
    await do(store, D.write_items(desk_id, items_of(desk["items"])))


def _broken(path, value, held=STRIP):
    """``held`` with the value at ``path`` set to ``value``, or deleted for ``...``."""
    held = copy.deepcopy(held)
    at = held
    for step in path[:-1]:
        at = at[step]
    if value is ...:
        del at[path[-1]]
    else:
        at[path[-1]] = value
    return held


# --- Desks -------------------------------------------------------------------------------


async def test_create_get_rename_list_delete_a_desk(store):
    assert await store.read(D.list_desks()) == []
    await do(store, D.create_desk("Runs", id="abcd1234"))
    assert await read(store, "abcd1234") == {"name": "Runs", "items": []}
    assert await store.read(D.list_desks()) == ["abcd1234"]
    await do(store, D.rename_desk("abcd1234", "Logs"))
    assert (await read(store, "abcd1234"))["name"] == "Logs"
    await do(store, D.delete_desk("abcd1234"))
    assert await store.read(D.list_desks()) == []
    assert is_null(await read(store, "abcd1234"))


async def test_a_desk_left_without_an_id_gets_one_minted(store):
    await do(store, D.create_desk("Runs"))
    (desk_id,) = await store.read(D.list_desks())
    assert DESK_ID.fullmatch(desk_id)


async def test_desks_list_in_placement_order_not_by_id(store):
    for desk_id in ("zzzz0001", "aaaa0002", "mmmm0003"):
        await do(store, D.create_desk(desk_id, id=desk_id))
    assert await store.read(D.list_desks()) == ["zzzz0001", "aaaa0002", "mmmm0003"]
    await do(store, D.create_desk("b", id="bbbb0004", before="aaaa0002"))
    await do(store, D.create_desk("c", id="cccc0005", after="zzzz0001"))
    assert await store.read(D.list_desks()) == [
        "zzzz0001",
        "cccc0005",
        "bbbb0004",
        "aaaa0002",
        "mmmm0003",
    ]


async def test_move_desk_puts_it_before_or_after_another_or_last(store):
    for desk_id in ("aaaa0001", "bbbb0002", "cccc0003"):
        await do(store, D.create_desk(desk_id, id=desk_id))
    await do(store, D.move_desk("cccc0003", before="aaaa0001"))
    assert await store.read(D.list_desks()) == ["cccc0003", "aaaa0001", "bbbb0002"]
    await do(store, D.move_desk("cccc0003"))
    assert await store.read(D.list_desks()) == ["aaaa0001", "bbbb0002", "cccc0003"]
    await do(store, D.move_desk("cccc0003"))
    assert await store.read(D.list_desks()) == ["aaaa0001", "bbbb0002", "cccc0003"]
    await do(store, D.move_desk("aaaa0001", after="bbbb0002"))
    assert await store.read(D.list_desks()) == ["bbbb0002", "aaaa0001", "cccc0003"]


async def test_a_moved_desk_keeps_its_items(store):
    await made(store, "aaaa0001")
    await do(store, D.create_desk("b", id="bbbb0002"))
    await do(store, D.move_desk("aaaa0001"))
    assert await read(store, "aaaa0001") == DESK


@pytest.mark.parametrize("desk_id", ["abc", "ABCD1234", "abcd-123", "abcd12345", ""])
async def test_create_refuses_an_id_spelled_wrong(store, desk_id):
    with pytest.raises(Refused):
        await do(store, D.create_desk("x", id=desk_id))


async def test_create_refuses_a_taken_id_or_a_missing_anchor(store):
    await made(store)
    with pytest.raises(Exists):
        await do(store, D.create_desk("x", id="abcd1234"))
    with pytest.raises(Missing):
        await do(store, D.create_desk("x", id="aaaa0001", before="zzzz9999"))
    assert await read(store, "abcd1234") == DESK
    assert await store.read(D.list_desks()) == ["abcd1234"]


async def test_desk_ops_raise_for_a_missing_desk(store):
    for term in (
        D.rename_desk("abcd1234", "x"),
        D.delete_desk("abcd1234"),
        D.move_desk("abcd1234"),
        D.save_desk("abcd1234"),
        D.add_item("abcd1234", PLANE),
        D.write_items("abcd1234", {}),
    ):
        with pytest.raises(Missing):
            await do(store, term)


async def test_a_desk_never_looks_up_its_planes(store):
    """No plane in DESK exists: the shape is all that is checked."""
    await made(store)
    assert await read(store, "abcd1234") == DESK


# --- Items -------------------------------------------------------------------------------


async def test_add_set_and_remove_items(store):
    await do(store, D.create_desk("Runs", id="abcd1234"))
    await do(store, D.add_item("abcd1234", PLANE, id="k3x9ab"))
    await do(store, D.add_item("abcd1234", STRIP, id="q7m2zz"))
    assert await read(store, "abcd1234") == {**DESK, "name": "Runs"}
    await do(store, D.add_item("abcd1234", plain("p9"), id="first0", before="k3x9ab"))
    await do(store, D.add_item("abcd1234", plain("p8"), id="middle", after="k3x9ab"))
    assert await ids(store, "abcd1234") == ["first0", "k3x9ab", "middle", "q7m2zz"]
    # A set replaces the item in its place.
    await do(store, D.set_item("abcd1234", "k3x9ab", plain("p5")))
    assert (await read(store, "abcd1234"))["items"][1] == {"id": "k3x9ab", **plain("p5")}
    await do(store, D.remove_item("abcd1234", "middle"))
    assert await ids(store, "abcd1234") == ["first0", "k3x9ab", "q7m2zz"]


async def test_add_mints_an_item_id_and_add_plane_makes_a_plane_item(store):
    await do(store, nuspace.plane.add("p1"))
    await do(store, D.create_desk("Runs", id="abcd1234"))
    await do(store, D.add_plane("abcd1234", "p1", {"run": "42"}))
    await do(store, D.add_plane("abcd1234", "p1"))
    first, second = (await read(store, "abcd1234"))["items"]
    assert first["id"] != second["id"]
    assert {k: v for k, v in first.items() if k != "id"} == {
        "kind": "plane",
        "original": link("p1", run="42"),
    }
    assert second["original"] == link("p1")
    with pytest.raises(Missing):
        await do(store, D.add_plane("abcd1234", "ghost"))


async def test_item_ops_refuse_what_they_cannot_do(store):
    await made(store)
    for term, error in (
        (D.add_item("abcd1234", PLANE, id="k3x9ab"), Exists),
        (D.add_item("abcd1234", PLANE, id="SHORT"), Refused),
        (D.add_item("abcd1234", {"kind": "pane"}), Refused),
        (D.add_item("abcd1234", PLANE, before="nope00"), Missing),
        (D.set_item("abcd1234", "nope00", PLANE), Missing),
        (D.set_item("abcd1234", "k3x9ab", {"kind": "pane"}), Refused),
        (D.remove_item("abcd1234", "nope00"), Missing),
        (D.move_item("abcd1234", "nope00"), Missing),
        (D.move_item("abcd1234", "k3x9ab", to="zzzz9999"), Missing),
        (D.move_item("abcd1234", "k3x9ab", before="k3x9ab"), Refused),
        (D.reset_item("abcd1234", "nope00"), Missing),
    ):
        with pytest.raises(error):
            await do(store, term)
    assert await read(store, "abcd1234") == DESK


async def test_move_item_within_its_desk(store):
    await made(store)
    await do(store, D.add_item("abcd1234", plain("p9"), id="third0"))
    await do(store, D.move_item("abcd1234", "third0", before="k3x9ab"))
    assert await ids(store, "abcd1234") == ["third0", "k3x9ab", "q7m2zz"]
    await do(store, D.move_item("abcd1234", "third0"))
    assert await ids(store, "abcd1234") == ["k3x9ab", "q7m2zz", "third0"]
    await do(store, D.move_item("abcd1234", "k3x9ab", after="q7m2zz"))
    assert await ids(store, "abcd1234") == ["q7m2zz", "k3x9ab", "third0"]


async def test_move_item_to_another_desk_keeps_its_id_and_links(store):
    await made(store)
    await do(store, D.create_desk("Other", id="other001"))
    await do(store, D.add_item("other001", plain("p9"), id="there0"))
    await do(store, D.move_item("abcd1234", "q7m2zz", to="other001", before="there0"))
    assert await ids(store, "abcd1234") == ["k3x9ab"]
    assert (await read(store, "other001"))["items"] == [
        {"id": "q7m2zz", **STRIP},
        {"id": "there0", **plain("p9")},
    ]
    # An id the other desk holds already is refused, and nothing moves.
    await do(store, D.add_item("abcd1234", plain("p7"), id="there0"))
    with pytest.raises(Exists):
        await do(store, D.move_item("abcd1234", "there0", to="other001"))
    assert await ids(store, "abcd1234") == ["k3x9ab", "there0"]


async def test_save_makes_every_recent_the_original(store):
    navigated = _broken(("columns", 0, "panes", 1, "recent"), link("p7"))
    desk = {"name": "Runs", "items": [{"id": "k3x9ab", **PLANE}, {"id": "q7m2zz", **navigated}]}
    await made(store, desk=desk)
    await do(store, D.save_desk("abcd1234"))
    items = (await read(store, "abcd1234"))["items"]
    assert items[0] == {"id": "k3x9ab", "kind": "plane", "original": link("p4", run="43")}
    assert items[1]["columns"][0]["panes"][1] == {"share": 0.4, "original": link("p7")}
    assert await ids(store, "abcd1234") == ["k3x9ab", "q7m2zz"]


async def test_reset_drops_the_recents_of_one_item(store):
    await made(store)
    await do(store, D.reset_item("abcd1234", "k3x9ab"))
    assert (await read(store, "abcd1234"))["items"][0] == {"id": "k3x9ab", **plain("p1")}


def test_a_reset_strip_showing_a_plane_twice_keeps_the_first_pane():
    """p2's pane navigated to p9 freed p2; the other pane took p2. A reset makes two p2."""
    navigated = _broken(("columns", 0, "panes", 0, "recent"), link("p9"))
    navigated = _broken(("columns", 1, "panes", 0, "original", "plane"), "p2", navigated)
    assert item_problem(navigated) == ""
    reset = reset_item(navigated)
    assert reset["kind"] == "strip"
    assert [p["original"]["plane"] for c in reset["columns"] for p in c["panes"]] == ["p2", "p3"]
    assert item_problem(reset) == ""


async def test_write_items_deletes_then_sets_then_orders(store):
    await made(store)
    sets = {"new000": plain("p9"), "k3x9ab": plain("p5")}
    await do(store, D.write_items("abcd1234", sets, ["q7m2zz", "gone00"], ["new000", "k3x9ab"]))
    assert (await read(store, "abcd1234"))["items"] == [
        {"id": "new000", **plain("p9")},
        {"id": "k3x9ab", **plain("p5")},
    ]
    # No order: a new id goes last, a set keeps its place.
    await do(store, D.write_items("abcd1234", {"last00": plain("p8"), "new000": plain("p7")}))
    assert await ids(store, "abcd1234") == ["new000", "k3x9ab", "last00"]


async def test_write_items_refuses_a_bad_item_and_writes_nothing(store):
    await made(store)
    for sets in ({"SHORT": plain("p1")}, {"good00": {"kind": "pane"}}):
        with pytest.raises(Refused):
            await do(store, D.write_items("abcd1234", sets, ["k3x9ab"]))
    assert await read(store, "abcd1234") == DESK


# --- The item shape ---------------------------------------------------------------------

BAD = [
    (PLANE, (), "not a dict"),
    (PLANE, ("id",), "k3x9ab"),
    (PLANE, ("kind",), "pane"),
    (PLANE, ("kind",), ...),
    (PLANE, ("original",), ...),
    (PLANE, ("original", "plane"), ""),
    (PLANE, ("original", "params"), {"k": 1}),
    (PLANE, ("recent", "extra"), 1),
    (PLANE, ("recent",), None),
    (PLANE, ("columns",), []),
    (PLANE, ("scroll",), 10),
    (STRIP, ("original",), link("p1")),
    (STRIP, ("columns",), []),
    (STRIP, ("columns",), ...),
    # A strip of one pane is a plane item: the browser never writes one.
    (STRIP, ("columns",), [{"panes": [{"share": 1, "original": link("p1")}]}]),
    (STRIP, ("columns", 0, "width"), 0),
    (STRIP, ("columns", 0, "width"), -40),
    (STRIP, ("columns", 0, "width"), True),
    (STRIP, ("columns", 0, "focus"), 0),
    (STRIP, ("columns", 0, "panes"), []),
    (STRIP, ("columns", 0, "panes", 0, "share"), 0.9),
    (STRIP, ("columns", 0, "panes", 0, "plane"), "p2"),
    (STRIP, ("columns", 0, "panes", 0, "original"), ...),
    (STRIP, ("columns", 0, "panes", 0, "params"), {}),
    # A strip never shows one plane twice: by originals, and by what a recent shows.
    (STRIP, ("columns", 1, "panes", 0, "original", "plane"), "p2"),
    (STRIP, ("columns", 0, "panes", 1, "recent"), link("p1")),
]


@pytest.mark.parametrize(("held", "path", "value"), BAD)
async def test_add_and_set_refuse_a_dict_that_is_not_an_item(store, held, path, value):
    item = value if not path else _broken(path, value, held)
    assert item_problem(item) != ""
    await made(store)
    with pytest.raises(Refused):
        await do(store, D.add_item("abcd1234", item))
    with pytest.raises(Refused):
        await do(store, D.set_item("abcd1234", "k3x9ab", item))
    assert await read(store, "abcd1234") == DESK


def test_a_strip_shows_a_plane_its_panes_navigated_away_from():
    """Twice is by what a pane shows: p2 navigated to p9 frees p2 for another pane."""
    moved = _broken(("columns", 0, "panes", 0, "recent"), link("p9"))
    moved = _broken(("columns", 1, "panes", 0, "original", "plane"), "p2", moved)
    assert item_problem(moved) == ""


def test_a_write_is_checked_whole():
    good = {"desk_id": "abcd1234", "sets": {"k3x9ab": PLANE}, "deletes": [], "order": []}
    assert write_problem(good) == ""
    assert write_problem({**good, "order": None}) == ""
    assert write_problem({k: v for k, v in good.items() if k != "order"}) == ""
    for broken in (
        {**good, "sets": {"SHORT": PLANE}},
        {**good, "sets": {"k3x9ab": {"kind": "pane"}}},
        {**good, "deletes": "k3x9ab"},
        {**good, "order": [1]},
        {**good, "desk_id": 3},
        {**good, "extra": 1},
        [],
    ):
        assert write_problem(broken) != ""


def test_order_moves_puts_the_named_ids_first_and_skips_the_rest():
    assert order_moves(["a", "b", "c"], ["a", "b", "c"]) == []
    assert order_moves(["a", "b", "c"], ["c", "a"]) == [["c", "before", "a"]]
    assert order_moves(["a", "b", "c"], ["b", "c", "a"]) == [
        ["b", "before", "a"],
        ["c", "after", "b"],
    ]
    assert order_moves(["a", "b"], ["x", "b", "b"]) == [["b", "before", "a"]]
    assert order_moves([], ["a"]) == []


def test_a_desk_reads_back_its_items_in_order_and_skips_one_off_the_shape():
    stored = {
        "name": "Runs",
        "entries": {"q7m2zz": STRIP, "bad000": {"kind": "x"}, "k3x9ab": PLANE},
    }
    assert desk_view(stored) == {
        "name": "Runs",
        "items": [{"id": "q7m2zz", **STRIP}, {"id": "k3x9ab", **PLANE}],
    }
    assert items_of(DESK["items"]) == {"k3x9ab": PLANE, "q7m2zz": STRIP}


def test_saved_entries_lists_only_the_items_with_a_recent():
    stored = {"name": "Runs", "entries": {"k3x9ab": PLANE, "q7m2zz": STRIP}}
    assert saved_entries(stored) == {"k3x9ab": {"kind": "plane", "original": link("p4", run="43")}}


# --- Roles -------------------------------------------------------------------------------


async def test_set_role_sets_and_changes_a_role(store):
    await do(store, nuspace.plane.add("p1"))
    await do(store, nuspace.plane.add("p2"))
    await do(store, web.set_role("home", "p1"))
    assert await store.read(web.Web.roles["home"]) == "p1"
    await do(store, web.set_role("home", "p2"))
    assert await store.read(web.Web.roles.extract()) == {"home": "p2"}


async def test_set_role_refuses_an_unknown_role_or_plane(store):
    await do(store, nuspace.plane.add("p1"))
    with pytest.raises(Refused, match="no role"):
        await do(store, web.set_role("dashboard", "p1"))
    with pytest.raises(Missing):
        await do(store, web.set_role("search", "ghost"))
    assert await store.read(web.Web.roles.extract()) == {}


# --- Seeding the role planes -------------------------------------------------------------


async def roles(store):
    return await store.read(web.Web.roles.extract())


async def test_ensure_without_roles_mints_a_system_web_plane_per_role(store):
    await store.run(ensure())
    held = await roles(store)
    assert set(held) == set(web.ROLES)
    assert len(set(held.values())) == 3
    for plane in held.values():
        assert plane.startswith("p_")
        assert await store.read(Space.planes[plane].system) is True
        assert await store.read(web.Web.planes.contains(plane)) is True
    await store.run(ensure())
    assert await roles(store) == held


async def test_ensure_leaves_a_role_that_is_set_alone(store):
    await do(store, nuspace.plane.add("mine", name="Mine", backend="async"))
    await do(store, web.set_role("home", "mine"))
    await store.run(ensure())
    held = await roles(store)
    assert held["home"] == "mine"
    assert await store.read(Space.planes["mine"].name) == "Mine"
    assert await store.read(Space.planes["mine"].cells.len()) == 0
    # The other two were made.
    assert held["search"].startswith("p_") and held["settings"].startswith("p_")


async def test_ensure_remakes_a_role_whose_plane_has_no_row(store):
    await store.run(ensure())
    await do(store, web.Web.roles.set_item("settings", "gone"))
    await store.run(ensure())
    held = await roles(store)
    assert held["settings"] not in ("gone", "")
    assert await store.read(Space.planes[held["settings"]].name) == "Settings"


async def test_ensure_mints_a_role_plane_even_with_a_plane_named_like_the_role(store):
    await do(store, nuspace.plane.add("home", backend="async"))
    await store.run(ensure())
    assert (await roles(store))["home"].startswith("p_")


# --- Favorites ----------------------------------------------------------------------------


async def _favorites(store) -> tuple[str, dict]:
    (desk_id,) = await store.read(D.list_desks())
    return desk_id, await read(store, desk_id)


async def test_ensure_seeds_an_empty_favorites_once_and_a_closed_one_stays_closed(store):
    await store.run(ensure())
    desk_id, desk = await _favorites(store)
    assert desk == {"name": "Favorites", "items": []}
    assert DESK_ID.fullmatch(desk_id)
    assert await store.read(web.Web.desks_seeded) is True
    await store.run(ensure())
    assert await store.read(D.list_desks()) == [desk_id]
    # Closed, it never comes back.
    await do(store, D.delete_desk(desk_id))
    await store.run(ensure())
    assert await store.read(D.list_desks()) == []


async def test_favorites_comes_first_on_a_new_space(store):
    await store.run(ensure())
    desk_id, _ = await _favorites(store)
    await do(store, D.create_desk("Runs", id="aaaa0001"))
    assert await store.read(D.list_desks()) == [desk_id, "aaaa0001"]


# --- The desks feed, one tab ---------------------------------------------------------------


class FakeSession(WsSession):
    """A session with no socket: frames sent are kept, notifies are fired by hand."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    def notify(self, op: str, payload: dict) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=("desks", "ops", op), payload=payload))

    def writes(self, op: str) -> list[dict]:
        return [
            f.payload
            for f in self.frames
            if f.ref == ("desks",) and isinstance(f.payload, dict) and f.payload.get("op") == op
        ]

    def toasts(self) -> list[dict]:
        return [f.payload for f in self.frames if f.ref == ("toast",) and f.payload]


#: A tab compiles its whole term before the first frame: slow on a loaded machine.
BOOT_TIMEOUT = 30.0


async def _until(check, timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


def _tab(store, sid):
    from nuspace.web.device import connection

    session = FakeSession()
    ctx = store.ctx.bind(Session, session)
    registry = space_registry(extensions=["testing"])
    task = asyncio.create_task(nu.arun(connection(nu.Str(sid), registry=registry), ctx))
    return session, task


def _desks(session):
    return session.writes("set_desks")[-1]["desks"]


async def test_two_tabs_get_desks_and_roles_live(store):
    await store.run(ensure())
    fav, favorites_desk = await _favorites(store)
    await do(store, nuspace.plane.add("p9", backend="async"))
    one, first = _tab(store, "s1")
    two, second = _tab(store, "s2")
    try:
        await _until(lambda: one.writes("set_desks") and two.writes("set_desks"), BOOT_TIMEOUT)
        await _until(lambda: one.writes("set_roles") and two.writes("set_roles"))
        assert _desks(one) == {fav: favorites_desk}
        assert one.writes("set_desks")[-1]["order"] == [fav]
        assert one.writes("set_roles")[-1]["roles"] == await roles(store)

        # A create in one tab reaches the other, after Favorites in the order.
        one.notify("desk.create", {"desk_id": "abcd1234", "desk": DESK})
        await _until(lambda: _desks(two) == {fav: favorites_desk, "abcd1234": DESK})
        assert two.writes("set_desks")[-1]["order"] == [fav, "abcd1234"]
        # A rename, everywhere, the writer's echo included.
        two.notify("desk.rename", {"desk_id": "abcd1234", "name": "Logs"})
        await _until(lambda: _desks(one).get("abcd1234", {}).get("name") == "Logs")
        await _until(lambda: _desks(two).get("abcd1234", {}).get("name") == "Logs")
        # A move ships the new order.
        one.notify("desk.move", {"desk_id": "abcd1234", "before": fav})
        await _until(lambda: two.writes("set_desks")[-1]["order"] == ["abcd1234", fav])
        one.notify("desk.move", {"desk_id": "abcd1234", "before": ""})
        await _until(lambda: two.writes("set_desks")[-1]["order"] == [fav, "abcd1234"])
        # One items write across two desks: a move, in one commit.
        one.notify(
            "items.write",
            {
                "writes": [
                    {"desk_id": "abcd1234", "sets": {}, "deletes": ["k3x9ab"], "order": []},
                    {"desk_id": fav, "sets": {"k3x9ab": PLANE}, "deletes": [], "order": []},
                ]
            },
        )
        await _until(lambda: _desks(two)[fav]["items"] == [{"id": "k3x9ab", **PLANE}])
        assert [i["id"] for i in _desks(two)["abcd1234"]["items"]] == ["q7m2zz"]
        # A role change ships the roles.
        one.notify("role.set", {"role": "home", "plane_id": "p9"})
        await _until(lambda: two.writes("set_roles")[-1]["roles"]["home"] == "p9")
        # A delete.
        two.notify("desk.delete", {"desk_id": "abcd1234"})
        await _until(lambda: set(_desks(one)) == {fav})
        assert one.toasts() == [] and two.toasts() == []

        # Refusals toast on the tab that sent them, write nothing, and the arm keeps listening.
        one.notify("desk.create", {"desk_id": "BAD", "desk": DESK})
        await _until(lambda: len(one.toasts()) == 1)
        assert one.toasts()[-1]["type"] == "Refused"
        one.notify("desk.rename", {"desk_id": "zzzz9999", "name": "x"})
        await _until(lambda: len(one.toasts()) == 2)
        assert one.toasts()[-1]["type"] == "Missing"
        bad = {"desk_id": fav, "sets": {"k3x9ab": {"kind": "pane"}}, "deletes": [], "order": []}
        drop = {"desk_id": fav, "sets": {}, "deletes": ["k3x9ab"], "order": []}
        one.notify("items.write", {"writes": [drop, bad]})
        await _until(lambda: len(one.toasts()) == 3)
        assert one.toasts()[-1]["type"] == "Refused"
        one.notify("role.set", {"role": "dashboard", "plane_id": "p9"})
        await _until(lambda: len(one.toasts()) == 4)
        assert one.toasts()[-1]["type"] == "Refused"
        one.notify("desk.delete", {})
        await _until(lambda: len(one.toasts()) == 5)
        assert one.toasts()[-1]["type"] == "ValueError"
        one.notify("items.write", {"writes": "nope"})
        await _until(lambda: len(one.toasts()) == 6)
        assert one.toasts()[-1]["type"] == "ValueError"
        assert two.toasts() == []
        assert await store.read(D.list_desks()) == [fav]
        # The refused write wrote nothing, its first half included.
        assert (await read(store, fav))["items"] == [{"id": "k3x9ab", **PLANE}]
    finally:
        for task in (first, second):
            task.cancel()
        await asyncio.gather(first, second, return_exceptions=True)


# --- Titles ------------------------------------------------------------------------------


async def test_titles_cover_the_planes_on_a_desk_originals_and_recents(store):
    from nuspace.web.desks.feed import titles

    await do(store, nuspace.plane.add("p1", name="Train run 42", icon="lucide:flame"))
    await do(store, nuspace.plane.add("p4", name="Train run 43"))
    await do(store, nuspace.plane.add("kid", parent="p1", name="Logs"))
    await do(store, nuspace.plane.add("p9", name="Not on a desk"))
    await do(store, nuspace.plane.add("p3", name="Gone"))
    await do(store, nuspace.plane.remove("p3"))
    await do(store, nuspace.plane.add("r1", name="Only a recent"))
    # p2 has no row: left out, as the removed p3. p4 is only a plane item's recent,
    # r1 only a pane's: both in.
    strip = _broken(("columns", 0, "panes", 0, "original", "plane"), "kid")
    strip = _broken(("columns", 0, "panes", 1, "recent"), link("r1"), strip)
    await made(
        store, desk={"name": "x", "items": [{"id": "k3x9ab", **PLANE}, {"id": "q7m2zz", **strip}]}
    )
    assert await store.read(titles()) == {
        "p1": {"title": "Train run 42", "icon": "lucide:flame"},
        "p4": {"title": "Train run 43", "icon": DEFAULT_ICON},
        "kid": {"title": "Logs", "icon": DEFAULT_ICON},
        "r1": {"title": "Only a recent", "icon": DEFAULT_ICON},
    }


async def test_titles_ship_live_and_again_on_a_rename_or_an_icon(store):
    await store.run(ensure())
    for plane in ("p1", "p2", "p3", "p9"):
        await do(store, nuspace.plane.add(plane, name=plane.upper()))
    one, task = _tab(store, "s1")

    def shipped():
        got = one.writes("set_titles")
        return got[-1]["titles"] if got else None

    try:
        await _until(lambda: shipped() is not None, BOOT_TIMEOUT)
        assert shipped() == {}
        one.notify("desk.create", {"desk_id": "abcd1234", "desk": DESK})
        looks = {p: {"title": p.upper(), "icon": DEFAULT_ICON} for p in ("p1", "p2", "p3")}
        await _until(lambda: shipped() == looks)
        await do(store, nuspace.plane.rename("p2", "Logs"))
        await _until(lambda: shipped()["p2"]["title"] == "Logs")
        await do(store, nuspace.plane.set_icon("p3", "lucide:flame"))
        await _until(lambda: shipped()["p3"]["icon"] == "lucide:flame")
        assert "p9" not in shipped()
        one.notify("desk.delete", {"desk_id": "abcd1234"})
        await _until(lambda: shipped() == {})
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
