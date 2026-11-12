"""``nuspace.devices.web`` desks and roles: the ops, the role planes' seeding, and the desks feed.

Every op is a bare term, run here inside ``nuspace.atomic`` as a caller
would. The feed runs in one tab over a fake session, as ``test_web.py``.
"""

from __future__ import annotations

import asyncio
import copy

import pytest

import nu
import nuspace
import nuspace.devices.web as web
from nu.lang import is_null
from nuspace.devices.web.desks.model import DESK_ID, desk_problem, favorites, moved_order
from nuspace.devices.web.planes import ensure
from nuspace.errors import Exists, Missing, Refused
from nuspace.shapes import Space
from nuspace.specs import space_registry
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")


def link(plane: str, **params: str) -> dict:
    return {"plane": plane, "params": params}


#: A desk of a plane item navigated away (original p1, recent p4), then a strip
#: of two columns: one of two panes, then one of p1 again (a plane may sit in
#: several items).
DESK = {
    "name": "Train run 42 + Logs",
    "items": [
        {"id": "k3x9ab", "kind": "plane", "original": link("p1"), "recent": link("p4", run="43")},
        {
            "id": "q7m2zz",
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
        },
    ],
}

#: A new desk: empty, and a desk all the same.
EMPTY = {"name": "New desk", "items": []}

#: A desk of iteration 1, strips of columns: dropped on read, never migrated.
OLD_DESK = {
    "name": "Old",
    "strips": [{"columns": [{"width": 1, "panes": [{"plane": "p1", "share": 1, "params": {}}]}]}],
}

#: A desk of iteration 2, columns at the top: dropped on read too.
OLD_COLUMNS = {
    "name": "Older",
    "columns": [
        {"width": 0.5, "panes": [{"plane": "p1", "share": 1, "params": {}}]},
        {"width": 0.5, "panes": [{"plane": "p2", "share": 1, "params": {}}]},
    ],
}


async def do(store, term):
    return await store.run(nuspace.atomic(term))


def _broken(path, value, desk=DESK):
    """``desk`` with the item at ``path`` set to ``value``, or deleted for ``...``."""
    desk = copy.deepcopy(desk)
    at = desk
    for step in path[:-1]:
        at = at[step]
    if value is ...:
        del at[path[-1]]
    else:
        at[path[-1]] = value
    return desk


# --- Desks -------------------------------------------------------------------------------


async def test_create_get_list_set_delete_a_desk(store):
    assert await store.read(web.desks.list_desks()) == []
    await do(store, web.desks.create_desk("abcd1234", DESK))
    assert await store.read(web.desks.get_desk("abcd1234")) == DESK
    assert await store.read(web.desks.list_desks()) == ["abcd1234"]
    renamed = {**DESK, "name": "Logs", "items": DESK["items"][:1]}
    await do(store, web.desks.set_desk("abcd1234", renamed))
    assert await store.read(web.desks.get_desk("abcd1234")) == renamed
    await do(store, web.desks.delete_desk("abcd1234"))
    assert await store.read(web.desks.list_desks()) == []
    assert await store.read(web.desks.desk_order()) == []
    assert is_null(await store.read(web.desks.get_desk("abcd1234")))


ACCEPTED = [
    EMPTY,
    DESK,
    # A plane item with no recent, beside one with: the same plane, twice in a desk.
    {"name": "x", "items": [*DESK["items"], {**DESK["items"][0], "id": "zz0000"}]},
    {"name": "x", "items": [{"id": "a00000", "kind": "plane", "original": link("p1")}]},
]


@pytest.mark.parametrize("desk", ACCEPTED)
async def test_a_desk_of_items_is_accepted_empty_or_not(store, desk):
    assert desk_problem(desk) == ""
    await do(store, web.desks.create_desk("abcd1234", desk))
    assert await store.read(web.desks.get_desk("abcd1234")) == desk
    await do(store, web.desks.set_desk("abcd1234", EMPTY))
    assert await store.read(web.desks.get_desk("abcd1234")) == EMPTY


async def test_desks_list_in_creation_order_not_by_id(store):
    for desk_id in ("zzzz0001", "aaaa0002", "mmmm0003"):
        await do(store, web.desks.create_desk(desk_id, EMPTY))
    assert await store.read(web.desks.list_desks()) == ["zzzz0001", "aaaa0002", "mmmm0003"]
    await do(store, web.desks.delete_desk("aaaa0002"))
    await do(store, web.desks.create_desk("aaaa0002", EMPTY))
    assert await store.read(web.desks.list_desks()) == ["zzzz0001", "mmmm0003", "aaaa0002"]
    # A desk a program stored straight, with no place in the order: after, by id.
    await do(store, web.Web.desks["bbbb0004"].set(EMPTY))
    assert await store.read(web.desks.list_desks()) == [
        "zzzz0001",
        "mmmm0003",
        "aaaa0002",
        "bbbb0004",
    ]


async def test_move_desk_puts_it_before_another_or_last(store):
    for desk_id in ("aaaa0001", "bbbb0002", "cccc0003"):
        await do(store, web.desks.create_desk(desk_id, EMPTY))
    await do(store, web.desks.move_desk("cccc0003", "aaaa0001"))
    assert await store.read(web.desks.list_desks()) == ["cccc0003", "aaaa0001", "bbbb0002"]
    await do(store, web.desks.move_desk("cccc0003", ""))
    assert await store.read(web.desks.list_desks()) == ["aaaa0001", "bbbb0002", "cccc0003"]
    # Before an unknown desk, or before itself: last too.
    await do(store, web.desks.move_desk("aaaa0001", "nope0000"))
    assert await store.read(web.desks.list_desks()) == ["bbbb0002", "cccc0003", "aaaa0001"]
    await do(store, web.desks.move_desk("cccc0003", "cccc0003"))
    assert await store.read(web.desks.list_desks()) == ["bbbb0002", "aaaa0001", "cccc0003"]
    with pytest.raises(Missing):
        await do(store, web.desks.move_desk("zzzz9999", ""))


def test_moved_order_places_a_desk_the_order_lacks_once():
    assert moved_order(["a", "b"], "c", "b") == ["a", "c", "b"]
    assert moved_order(["a", "b", "a"], "a", "") == ["b", "a"]
    assert moved_order(None, "a", "") == ["a"]


@pytest.mark.parametrize("desk_id", ["abc", "ABCD1234", "abcd-123", "abcd12345", ""])
async def test_create_refuses_an_id_spelled_wrong(store, desk_id):
    with pytest.raises(Refused, match="8 chars"):
        await do(store, web.desks.create_desk(desk_id, DESK))


async def test_create_refuses_a_taken_id(store):
    await do(store, web.desks.create_desk("abcd1234", DESK))
    with pytest.raises(Exists):
        await do(store, web.desks.create_desk("abcd1234", EMPTY))
    assert await store.read(web.desks.get_desk("abcd1234")) == DESK
    assert await store.read(web.desks.desk_order()) == ["abcd1234"]


async def test_set_and_delete_raise_for_a_missing_desk(store):
    with pytest.raises(Missing):
        await do(store, web.desks.set_desk("abcd1234", DESK))
    with pytest.raises(Missing):
        await do(store, web.desks.delete_desk("abcd1234"))


STRIP = ("items", 1, "columns")

BAD = [
    ((), "not a dict"),
    ((), OLD_DESK),
    ((), OLD_COLUMNS),
    (("focus",), 0),
    (("columns",), []),
    (("name",), ...),
    (("name",), 3),
    (("items",), ...),
    (("items",), {}),
    (("items", 0), "k3x9ab"),
    (("items", 0, "kind"), "pane"),
    (("items", 0, "kind"), ...),
    (("items", 0, "id"), "short"),
    (("items", 0, "id"), "K3X9AB"),
    (("items", 0, "id"), 7),
    (("items", 1, "id"), "k3x9ab"),
    (("items", 0, "original"), ...),
    (("items", 0, "original", "plane"), ""),
    (("items", 0, "original", "params"), {"k": 1}),
    (("items", 0, "recent", "extra"), 1),
    (("items", 0, "recent"), None),
    (("items", 0, "columns"), []),
    (("items", 0, "scroll"), 10),
    (("items", 1, "original"), link("p1")),
    ((*STRIP,), []),
    ((*STRIP,), ...),
    # A strip of one pane is a plane item: the browser never writes one.
    ((*STRIP,), [{"panes": [{"share": 1, "original": link("p1")}]}]),
    ((*STRIP, 0, "width"), 0),
    ((*STRIP, 0, "width"), -40),
    ((*STRIP, 0, "width"), True),
    ((*STRIP, 0, "focus"), 0),
    ((*STRIP, 0, "panes"), []),
    ((*STRIP, 0, "panes", 0, "share"), 0.9),
    ((*STRIP, 0, "panes", 0, "plane"), "p2"),
    ((*STRIP, 0, "panes", 0, "original"), ...),
    ((*STRIP, 0, "panes", 0, "params"), {}),
    # A strip never shows one plane twice: by originals, and by what a recent shows.
    ((*STRIP, 1, "panes", 0, "original", "plane"), "p2"),
    ((*STRIP, 0, "panes", 1, "recent"), link("p1")),
]


@pytest.mark.parametrize(("path", "value"), BAD)
async def test_create_and_set_refuse_a_dict_that_is_not_a_desk(store, path, value):
    desk = value if not path else _broken(path, value)
    assert desk_problem(desk) != ""
    with pytest.raises(Refused):
        await do(store, web.desks.create_desk("abcd1234", desk))
    await do(store, web.desks.create_desk("abcd1234", DESK))
    with pytest.raises(Refused):
        await do(store, web.desks.set_desk("abcd1234", desk))
    assert await store.read(web.desks.get_desk("abcd1234")) == DESK


def test_a_strip_shows_a_plane_its_panes_navigated_away_from():
    """Twice is by what a pane shows: p2 navigated to p9 frees p2 for another pane."""
    moved = _broken((*STRIP, 0, "panes", 0, "recent"), link("p9"))
    moved = _broken((*STRIP, 1, "panes", 0, "original", "plane"), "p2", moved)
    assert desk_problem(moved) == ""


async def test_a_desk_in_an_older_shape_reads_as_no_desk(store):
    await do(store, web.Web.desks["olddesk1"].set(OLD_DESK))
    await do(store, web.Web.desks["olddesk2"].set(OLD_COLUMNS))
    await do(store, web.desks.create_desk("abcd1234", DESK))
    assert await store.read(web.desks.list_desks()) == ["abcd1234"]
    assert is_null(await store.read(web.desks.get_desk("olddesk1")))
    assert is_null(await store.read(web.desks.get_desk("olddesk2")))
    with pytest.raises(Refused):
        await do(store, web.desks.set_desk("olddesk2", OLD_COLUMNS))


async def test_a_desk_never_looks_up_its_planes(store):
    """No plane in DESK exists: the shape is all that is checked."""
    await do(store, web.desks.create_desk("abcd1234", DESK))
    assert await store.read(web.desks.list_desks()) == ["abcd1234"]


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
    (desk_id,) = await store.read(web.desks.list_desks())
    return desk_id, await store.read(web.desks.get_desk(desk_id))


async def test_ensure_seeds_an_empty_favorites_once_and_a_closed_one_stays_closed(store):
    await store.run(ensure())
    desk_id, desk = await _favorites(store)
    assert desk == {"name": "Favorites", "items": []}
    assert DESK_ID.fullmatch(desk_id)
    assert await store.read(web.Web.seeded) is True
    await store.run(ensure())
    assert await store.read(web.desks.list_desks()) == [desk_id]
    # Closed, it never comes back.
    await do(store, web.desks.delete_desk(desk_id))
    await store.run(ensure())
    assert await store.read(web.desks.list_desks()) == []


async def test_favorites_comes_first_in_creation_order(store):
    await store.run(ensure())
    desk_id, _ = await _favorites(store)
    await do(store, web.desks.create_desk("aaaa0001", EMPTY))
    assert await store.read(web.desks.list_desks()) == [desk_id, "aaaa0001"]


def test_favorites_is_empty_its_id_minted_as_the_browser_does():
    made = favorites()
    assert DESK_ID.fullmatch(made["id"])
    assert made["desk"] == {"name": "Favorites", "items": []}
    assert desk_problem(made["desk"]) == ""


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
    from nuspace.devices.web.device import connection

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
    # Desks stored in an older shape are never shipped.
    await do(store, web.Web.desks["olddesk1"].set(OLD_DESK))
    await do(store, web.Web.desks["olddesk2"].set(OLD_COLUMNS))
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
        # A set replaces the desk whole, everywhere, the writer's echo included.
        renamed = {**DESK, "name": "Logs"}
        two.notify("desk.set", {"desk_id": "abcd1234", "desk": renamed})
        await _until(lambda: _desks(one).get("abcd1234") == renamed)
        await _until(lambda: _desks(two).get("abcd1234") == renamed)
        # An empty desk is a desk.
        one.notify("desk.set", {"desk_id": "abcd1234", "desk": EMPTY})
        await _until(lambda: _desks(two).get("abcd1234") == EMPTY)
        # A role change ships the roles.
        one.notify("role.set", {"role": "home", "plane_id": "p9"})
        await _until(lambda: two.writes("set_roles")[-1]["roles"]["home"] == "p9")
        # A delete.
        two.notify("desk.delete", {"desk_id": "abcd1234"})
        await _until(lambda: _desks(one) == {fav: favorites_desk})
        assert one.toasts() == [] and two.toasts() == []

        # Refusals toast on the tab that sent them, and the arm keeps listening.
        one.notify("desk.create", {"desk_id": "BAD", "desk": DESK})
        await _until(lambda: len(one.toasts()) == 1)
        assert one.toasts()[-1]["type"] == "Refused"
        one.notify("desk.set", {"desk_id": "zzzz9999", "desk": DESK})
        await _until(lambda: len(one.toasts()) == 2)
        assert one.toasts()[-1]["type"] == "Missing"
        one.notify("desk.create", {"desk_id": "abcd1234", "desk": {"name": "x"}})
        await _until(lambda: len(one.toasts()) == 3)
        assert one.toasts()[-1]["type"] == "Refused"
        one.notify("role.set", {"role": "dashboard", "plane_id": "p9"})
        await _until(lambda: len(one.toasts()) == 4)
        assert one.toasts()[-1]["type"] == "Refused"
        one.notify("desk.delete", {})
        await _until(lambda: len(one.toasts()) == 5)
        assert one.toasts()[-1]["type"] == "ValueError"
        assert two.toasts() == []
        assert await store.read(web.desks.list_desks()) == [fav]
        shipped = one.writes("set_desks")
        assert all({"olddesk1", "olddesk2"}.isdisjoint(w["desks"]) for w in shipped)
    finally:
        for task in (first, second):
            task.cancel()
        await asyncio.gather(first, second, return_exceptions=True)


# --- Titles ------------------------------------------------------------------------------


async def test_titles_cover_the_planes_on_a_desk_originals_and_recents(store):
    from nuspace.devices.web.desks.feed import titles

    await do(store, nuspace.plane.add("p1", name="Train run 42", icon="lucide:flame"))
    await do(store, nuspace.plane.add("p4", name="Train run 43"))
    await do(store, nuspace.plane.add("kid", parent="p1", name="Logs"))
    await do(store, nuspace.plane.add("p9", name="Not on a desk"))
    await do(store, nuspace.plane.add("p3", name="Gone"))
    await do(store, nuspace.plane.remove("p3"))
    await do(store, nuspace.plane.add("r1", name="Only a recent"))
    # p2 has no row: left out, as the removed p3. p4 is only a plane item's recent,
    # r1 only a pane's: both in.
    desk = _broken((*STRIP, 0, "panes", 0, "original", "plane"), "kid")
    desk = _broken((*STRIP, 0, "panes", 1, "recent"), link("r1"), desk)
    await do(store, web.desks.create_desk("abcd1234", desk))
    # Desks in an older shape are skipped, their planes with them.
    await do(
        store,
        web.Web.desks["olddesk2"].set(
            _broken(("columns", 0, "panes", 0, "plane"), "p9", OLD_COLUMNS)
        ),
    )
    assert await store.read(titles()) == {
        "p1": {"title": "Train run 42", "icon": "lucide:flame"},
        "p4": {"title": "Train run 43", "icon": ""},
        "kid": {"title": "Logs", "icon": ""},
        "r1": {"title": "Only a recent", "icon": ""},
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
        looks = {p: {"title": p.upper(), "icon": ""} for p in ("p1", "p2", "p3")}
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
