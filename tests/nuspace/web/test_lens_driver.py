"""The lens surface, proved against a real server over a real websocket.

Same ground as ``test_apps_driver``: one process, one store, one uvicorn,
``websockets`` clients standing in for browser tabs. Nothing is mocked and no
driver function is called directly -- the navigation is a notify frame on the
op's own wire path, and every column asserted came back over the socket.

What is mounted is the **whole space**, ``space_driver``, so the lens arm is
proved in the composition it ships in. The store is seeded by driving the
apps surface first, which is also the point: the lens browses the same
``Space`` the other two surfaces are writing, with no store code of its own.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest
import websockets

import nu
import nu.kv
from nu.ui.core.protocol import OP_MOUNT, OP_NOTIFY, OP_READ, Frame, decode, encode
from nuspace.apps import free_port
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID
from nuspace.web import NuspaceShell, server, space_driver
from nuspace.web.lens import DEFAULT_MAX_ROWS


#: Wire paths the mount assigns. Asserted, not assumed.
LENS = "LensScreen.lens"
APPS = "AppsScreen.apps"

#: How long a client waits for the frames one op produces to stop arriving.
QUIET = 0.5

SRC = "def out(path):\n    return None\n"


class Browser:
    """A websocket client behaving the way the real browser's store does.

    Answers ``read`` with its own route and keeps the last lens payload, so a
    test asserts on traffic rather than only on end state.
    """

    def __init__(self, ws):
        self.ws = ws
        # The pages half of the composition reads this. The lens never does:
        # the cursor is its own, and it rides in every notify.
        self.route = {"top": "lens", "page_id": ROOT_PAGE_ID}
        self.frames = []
        self.lens = None

    async def _take(self, timeout):
        frame = decode(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
        if frame.op == OP_READ:
            await self.ws.send(
                encode(Frame(OP_READ, ref=frame.ref, payload=dict(self.route), id=frame.id))
            )
        elif frame.ref == LENS:
            self.lens = frame.payload or {}
        self.frames.append(frame)
        return frame

    async def mount(self):
        """The first frame, which is always the mount envelope."""
        frame = await self._take(5.0)
        assert frame.op == OP_MOUNT
        return frame.payload

    async def settle(self, quiet=QUIET):
        """Read until nothing has arrived for ``quiet`` seconds."""
        while True:
            try:
                await self._take(quiet)
            except TimeoutError:
                return

    async def notify(self, ref, op, **args):
        """Send one op on its own wire path, then let the answer settle."""
        await self.ws.send(encode(Frame(OP_NOTIFY, ref=f"{ref}.ops.{op}", payload=args)))
        await self.settle()

    async def go(self, *path):
        """Navigate the lens to ``path`` and return the columns that came back."""
        await self.notify(LENS, "nav", path=list(path))
        assert self.lens is not None
        # The echo is the frame arriving: a navigation whose answer never came
        # would otherwise read as the previous cascade being right.
        assert self.lens["path"] == list(path)
        return self.lens

    def keys(self, column):
        """The keys of one column of the last cascade."""
        return [e["key"] for e in self.lens["columns"][column]["entries"]]


def _driver(_address):
    """A fresh driver per connection. No section runs here, so no address."""
    return space_driver()


def _space(port, body):
    """One store, one server, one body. Brackets tear down LIFO when it ends."""
    return nu.With(
        nu.kv.memory_navigator(tags=(Space,)),
        server(_driver, shell_cls=NuspaceShell, host="127.0.0.1", port=port, open_browser=False),
        body=body,
    )


async def _await_port(port, attempts=100):
    """Wait until uvicorn is accepting, then let go of the socket."""
    for _ in range(attempts):
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", port)
        except OSError:
            await asyncio.sleep(0.05)
            continue
        del reader
        writer.close()
        await writer.wait_closed()
        return
    raise AssertionError(f"nothing listening on {port}")


def _walk(term, seen=None):
    """Every Nu node in a tree, once."""
    seen = set() if seen is None else seen
    if id(term) in seen:
        return
    seen.add(id(term))
    yield term
    for child in getattr(term, "_children", ()) or ():
        yield from _walk(child, seen)


def _assert_flat(tree, arms):
    """N reactive arms, no dispatch, no python in an atom."""
    nodes = list(_walk(tree))
    assert len([n for n in nodes if isinstance(n, nu.ReactForever)]) == arms

    # No branching on a kind. The lens has no guard either: a bad segment is
    # answered with an error column built while the term was, not with an
    # `IfDo` asking the store whether the browser was right.
    assert not [n for n in nodes if isinstance(n, (nu.Switch, nu.SwitchDo))]

    # Nothing smuggles a python function into an atom's payload. Classes are
    # allowed: a Shape class is an address, not behaviour. `LensColumns` and
    # `LensCell` hold none either -- an `InteractionFactory` atom closes over
    # its callable at class-definition time and its payload is the arity.
    for node in nodes:
        for value in (getattr(node, "_payload", None) or {}).values():
            assert isinstance(value, type) or not callable(value), (
                f"{type(node).__name__} carries {value!r}"
            )


def test_the_lens_driver_is_one_arm_and_nothing_else():
    """The thesis, pinned."""
    from nuspace.web.lens import ARMS, lens_driver
    from nuspace.web.space import LensScreen

    _assert_flat(lens_driver(LensScreen.lens), ARMS)


def test_the_three_drivers_fold_into_one_tree_with_every_arm_of_each():
    """The assembly adds nothing and drops nothing: it is a fold."""
    from nuspace.web.apps.driver import ARMS as APPS_ARMS
    from nuspace.web.lens.driver import ARMS as LENS_ARMS
    from nuspace.web.pages.driver import ARMS as PAGES_ARMS

    _assert_flat(space_driver(), APPS_ARMS + PAGES_ARMS + LENS_ARMS)


def test_no_two_arms_in_the_composition_bind_one_attrs_key():
    """Parallel arms share one ``ctx.attrs``, so no two may bind one key."""
    keys = [
        n._children[2]._payload["value"]
        for n in _walk(space_driver())
        if isinstance(n, nu.ReactForever) and n._payload["has_changed_key"]
    ]
    assert "lens_nav" in keys
    assert len(keys) == len(set(keys))


def test_the_composed_tree_still_passes_every_law():
    """An ``Eval`` is a Dynamic, and where it may sit is a law, not a taste."""
    from nu.lang import compile, validate

    validate(compile(space_driver()))


@pytest.mark.timeout(180)
async def test_the_whole_lens_loop_runs_over_one_websocket():
    port = free_port()
    task = asyncio.create_task(
        nu.arun(_space(port, nu.Delay(120.0)), nu.Context(), max_parallel=64)
    )
    try:
        await _await_port(port)
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Browser(ws)
            mount = await tab.mount()
            await tab.settle()

            # The ref is where the shell says it is, which is what every op
            # path below is built from.
            screens = {s["route"]: s for s in mount["pages"]}
            assert set(screens) == {"/apps", "/pages", "/lens"}
            (field,) = screens["/lens"]["fields"]
            assert field["path"] == LENS
            assert field["type"] == "LensRef"
            # The cap rides in the mount so the browser seeds with the same
            # number the server clips to. Two places name it -- the ref's
            # props and the driver's kwarg -- and the stock shell takes the
            # default in both, so this is what pins them together.
            assert field["props"]["max_rows"] == DEFAULT_MAX_ROWS

            # -- boot: the root column, unasked for --------------------------
            assert tab.lens["op"] == "set_columns"
            assert tab.lens["path"] == []
            assert len(tab.lens["columns"]) == 1
            root = tab.lens["columns"][0]
            assert root["kind"] == "shape"
            assert [e["key"] for e in root["entries"]] == ["apps", "pages", "state"]
            assert root["total"] == 3
            # A shape slot is a door, not a value: it says what kind of column
            # it opens and reads nothing.
            assert {e["kind"] for e in root["entries"]} == {"mapping"}
            assert all(e["navigable"] for e in root["entries"])

            # -- something to look at ----------------------------------------
            for aid, name in (("a_one", "One"), ("a_two", "Two")):
                await tab.notify(APPS, "app.create", app_id=aid, name=name, source=SRC)

            # -- drill: root -> apps -----------------------------------------
            await tab.go("apps")
            assert tab.lens["path"] == ["apps"]
            assert len(tab.lens["columns"]) == 2
            assert tab.keys(0) == ["apps", "pages", "state"]
            assert tab.lens["columns"][1]["kind"] == "mapping"
            assert tab.keys(1) == ["a_one", "a_two"]
            assert tab.lens["columns"][1]["total"] == 2
            # The values are Shapes, so a key is navigable and carries no value.
            assert {e["kind"] for e in tab.lens["columns"][1]["entries"]} == {"shape"}

            # -- drill: apps -> a_one ----------------------------------------
            await tab.go("apps", "a_one")
            assert len(tab.lens["columns"]) == 3
            col = tab.lens["columns"][2]
            assert col["kind"] == "shape"
            rows = {e["key"]: e for e in col["entries"]}
            assert {"name", "snippet", "policy"} <= set(rows)
            # A shape's leaf slots carry their value; that is the whole point
            # of a lens over a store and it is one ref read each.
            assert rows["name"]["preview"] == "One"
            assert rows["name"]["vtype"] == "str"

            # -- drill: a_one -> name (a leaf) --------------------------------
            await tab.go("apps", "a_one", "name")
            assert len(tab.lens["columns"]) == 4
            leaf = tab.lens["columns"][3]
            assert leaf["kind"] == "leaf"
            assert leaf["total"] == 1
            (cell,) = leaf["entries"]
            assert cell["key"] == "value"
            assert cell["text"] == "One"
            assert cell["clipped"] is False
            assert cell["navigable"] is False

            # -- pop back, twice ----------------------------------------------
            await tab.go("apps", "a_one")
            assert len(tab.lens["columns"]) == 3
            await tab.go("apps")
            assert len(tab.lens["columns"]) == 2
            assert tab.keys(1) == ["a_one", "a_two"]

            # -- the store moved under a standing cursor ----------------------
            # No subscription, by design. The next navigation is what shows it.
            await tab.notify(APPS, "app.delete", app_id="a_two")
            await tab.go("apps")
            assert tab.keys(1) == ["a_one"]

            # -- a second tab, its own cursor, having seen none of this -------
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws2:
                other = Browser(ws2)
                await other.mount()
                await other.settle()
                # Its own driver boots it at root: the server holds no cursor.
                assert other.lens["path"] == []
                await other.go("apps", "a_one", "name")
                assert other.lens["columns"][3]["entries"][0]["text"] == "One"
                # And the first tab did not move.
                assert tab.lens["path"] == ["apps"]
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


@pytest.mark.timeout(120)
async def test_a_path_that_names_nothing_leaves_the_arm_alive():
    """A bad crumb costs one column, not the surface and not the socket."""
    port = free_port()
    task = asyncio.create_task(nu.arun(_space(port, nu.Delay(90.0)), nu.Context(), max_parallel=64))
    try:
        await _await_port(port)
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Browser(ws)
            await tab.mount()
            await tab.settle()

            await tab.go("nosuchslot")
            assert len(tab.lens["columns"]) == 2
            broken = tab.lens["columns"][1]
            assert broken["entries"][0]["vtype"] == "error"
            # The columns to its left survived it.
            assert tab.keys(0) == ["apps", "pages", "state"]

            # Same arm, a real path this time.
            await tab.go("apps")
            assert tab.lens["columns"][1]["kind"] == "mapping"
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
