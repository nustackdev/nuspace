"""The apps surface, proved against a real server over a real websocket.

Same ground as ``test_pages_driver``: one process, one store, one uvicorn,
``websockets`` clients standing in for browser tabs. Nothing is mocked and no
driver function is called directly -- every write is a notify frame on that
op's own wire path, and everything asserted came back over the socket.

What is mounted here is the **whole space**, ``space_driver``, so the apps
arms are proved in the composition they actually ship in: every surface,
every driver, one shell, one ws. The loop is create, rename, edit the snippet,
restart, delete, and then a **second connection** opens, gets its own driver,
and boots from the same store having seen none of the traffic.

Nothing supervises these apps: no worker pool, no ``apps.runner``. That is
what ``attached=False`` says on the wire, and it is why every status reads
``idle`` rather than ``running``.
"""

from __future__ import annotations

import asyncio
import contextlib

import pytest
import websockets

import nu
import nu.kv
from nu.ui.core.protocol import OP_INIT, OP_NOTIFY, OP_READ, OP_WRITE, Frame, decode, encode
from nuspace.apps import free_port
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID
from nuspace.web import NuspaceShell, server, space_driver


#: Where the chain puts the apps surface: the screen slot, then the ref.
REF = ("apps", "apps")

#: The chrome a fresh connection is sent, one ``init`` per slot the shell
#: declares. What a tab reads before anything else arrives.
BOOT = NuspaceShell._boot_chains()

#: How long a client waits for the frames one op produces to stop arriving.
QUIET = 0.5

SRC = "def out():\n    return None\n"


class Browser:
    """A websocket client behaving the way the real browser's store does.

    Answers ``read`` with its own route, keeps the last payload per write op,
    and collects every frame so a test can assert on traffic rather than only
    on end state.
    """

    def __init__(self, ws):
        self.ws = ws
        # The pages half of the composition reads this. Apps never do: the
        # surface is flat and every frame carries the whole list.
        self.route = {"top": "apps", "page_id": ROOT_PAGE_ID}
        self.frames = []
        self.last = {}

    async def _take(self, timeout):
        frame = decode(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
        if frame.op == OP_READ:
            await self.ws.send(
                encode(Frame(OP_READ, ref=frame.ref, payload=dict(self.route), id=frame.id))
            )
        elif frame.op == OP_WRITE and frame.ref == REF:
            # Filtered by ref, not just by op: both surfaces ship a write
            # tagged `set_status`, and the real browser tells them apart the
            # same way -- a payload is handled by the node it landed on.
            payload = frame.payload or {}
            self.last[str(payload.get("op"))] = payload
        self.frames.append(frame)
        return frame

    async def boot(self):
        """The opening batch: a clearing remove, then one init per slot.

        Comes back as ``{path: (segment, type, props)}`` -- the leaf of every
        chain, which is where a surface's declared props ride in.
        """
        frames = [await self._take(5.0) for _ in range(len(BOOT) + 1)]
        assert [f.op for f in frames[1:]] == [OP_INIT] * len(BOOT)
        return {tuple(seg for seg, _, _ in f.chain): f.chain[-1] for f in frames[1:]}

    async def settle(self, quiet=QUIET):
        """Read until nothing has arrived for ``quiet`` seconds."""
        while True:
            try:
                await self._take(quiet)
            except TimeoutError:
                return

    async def notify(self, op, **args):
        """Send one op on its own wire path, then let the answer settle."""
        # The op name stays one segment, dots and all.
        await self.ws.send(encode(Frame(OP_NOTIFY, ref=[*REF, "ops", op], payload=args)))
        await self.settle()

    def rows(self):
        """The rail as ``{app_id: row}``, from the last ``set_apps``."""
        return {a["id"]: a for a in self.last["set_apps"]["apps"]}

    def states(self):
        """What the last ``set_status`` said, as ``{app_id: state}``."""
        return {s["section_id"]: s["state"] for s in self.last["set_status"]["statuses"]}


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

    # No branching on a kind. Guards (`IfDo`) are allowed and dispatch is not:
    # an IfDo asks whether an app is there, a Switch asks which op this is.
    assert not [n for n in nodes if isinstance(n, (nu.Switch, nu.SwitchDo))]

    # Nothing smuggles a python function into an atom's payload. Classes are
    # allowed: a Shape class is an address, not behaviour.
    for node in nodes:
        for value in (getattr(node, "_payload", None) or {}).values():
            assert isinstance(value, type) or not callable(value), (
                f"{type(node).__name__} carries {value!r}"
            )


def test_the_apps_driver_is_a_flat_fold_of_arms_and_nothing_else():
    """The thesis, pinned, for both the detached and the supervised build."""
    from nuspace.web.apps import ARMS, apps_driver
    from nuspace.web.space import AppsScreen

    _assert_flat(apps_driver(AppsScreen.apps), ARMS)
    # `attached=True` adds a mem read per status row, not an arm and not a
    # branch on anything the browser said.
    _assert_flat(apps_driver(AppsScreen.apps, attached=True), ARMS)


def test_every_driver_folds_into_one_tree_with_every_arm_of_each():
    """The assembly adds nothing and drops nothing: it is a fold."""
    from nuspace.web.apps.driver import ARMS as APPS_ARMS
    from nuspace.web.lens.driver import ARMS as LENS_ARMS
    from nuspace.web.pages.driver import ARMS as PAGES_ARMS

    _assert_flat(space_driver(), APPS_ARMS + PAGES_ARMS + LENS_ARMS)


def test_every_event_arm_has_its_own_attrs_namespace():
    """Parallel arms share one ``ctx.attrs``, so no two may bind one key.

    Both drivers fold into one ``Parallel``, so this is a claim about the
    composition rather than about either half: apps arms are prefixed
    ``app_`` for exactly this reason.
    """
    from nuspace.web.apps.driver import ARMS as APPS_ARMS

    keys = [
        n._children[2]._payload["value"]
        for n in _walk(space_driver())
        if isinstance(n, nu.ReactForever) and n._payload["has_changed_key"]
    ]
    # Every event arm binds one; the state arms deliberately bind none.
    assert len(keys) >= APPS_ARMS - 3
    assert len(keys) == len(set(keys))


@pytest.mark.timeout(180)
async def test_the_whole_app_loop_runs_over_one_websocket():
    port = free_port()
    # A long body: the server lives as long as the script needs, and the tree
    # is cancelled from outside rather than racing a timer it cannot see.
    task = asyncio.create_task(
        nu.arun(_space(port, nu.Delay(120.0)), nu.Context(), max_parallel=64)
    )
    try:
        await _await_port(port)
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Browser(ws)
            slots = await tab.boot()
            await tab.settle()

            # The ref is where its chain says it is, which is what every op
            # path below is built from. Three screens, one surface each.
            assert {p for p in slots if len(p) == 2} == {REF, ("pages", "pages"), ("lens", "lens")}
            assert slots[REF][1] == "AppsRef"
            # What a new app starts life as rides in the chain, so the browser
            # fills `source` on a create without owning a template.
            assert slots[REF][2]["starter"].startswith("import nu")

            # A cold store boots itself, and says out loud that nothing is
            # supervising these apps.
            assert tab.rows() == {}
            assert tab.last["set_apps"]["attached"] is False

            # -- create two apps -------------------------------------------------
            for aid, name, source in (("a_one", "One", SRC), ("a_two", "Two", "other")):
                await tab.notify("app.create", app_id=aid, name=name, source=source)
            rows = tab.rows()
            assert list(rows) == ["a_one", "a_two"]
            assert rows["a_one"]["name"] == "One"
            assert rows["a_two"]["source"] == "other"
            # Every app carries the default policy: nothing on this wire sets it.
            assert {r["policy"] for r in rows.values()} == {"always"}

            # -- rename --------------------------------------------------------
            await tab.notify("app.rename", app_id="a_one", name="Renamed")
            assert tab.rows()["a_one"]["name"] == "Renamed"

            # -- edit one snippet ------------------------------------------------
            await tab.notify("app.update", app_id="a_one", source="edited")
            assert tab.rows()["a_one"]["source"] == "edited"
            # And only that one.
            assert tab.rows()["a_two"]["source"] == "other"

            # -- select ----------------------------------------------------------
            await tab.notify("app.select", app_id="a_one")
            assert tab.states() == {"a_one": "idle", "a_two": "idle"}

            # -- restart ---------------------------------------------------------
            # A restart is a write and nothing else: the snippet goes back
            # unchanged, which is what the runner's own subscription hears.
            # Here nobody is listening, so what is observable is that the
            # store moved and the source survived.
            tab.last.pop("set_apps")
            await tab.notify("app.restart", app_id="a_one")
            assert tab.rows()["a_one"]["source"] == "edited"

            # -- a second tab, booting from the store, having seen none of this --
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws2:
                other = Browser(ws2)
                await other.boot()
                await other.settle()
                # Its own driver, and the store agrees with everything the
                # first tab was told.
                assert list(other.rows()) == ["a_one", "a_two"]
                assert other.rows()["a_one"]["name"] == "Renamed"
                assert other.rows()["a_one"]["source"] == "edited"
                assert other.states() == {"a_one": "idle", "a_two": "idle"}

                # -- delete, watched from both -------------------------------
                await tab.notify("app.delete", app_id="a_two")
                await other.settle()
                assert list(tab.rows()) == ["a_one"]
                assert list(other.rows()) == ["a_one"]

            # Both write verbs the surface has came back on the wire.
            assert {"set_apps", "set_status"} <= set(tab.last)
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


@pytest.mark.timeout(120)
async def test_a_bad_app_event_leaves_every_other_arm_alive():
    """One arm's body raising must not end the composition, or close the ws."""
    port = free_port()
    task = asyncio.create_task(nu.arun(_space(port, nu.Delay(90.0)), nu.Context(), max_parallel=64))
    try:
        await _await_port(port)
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Browser(ws)
            await tab.boot()
            await tab.settle()

            # An empty app id is not a kv key, so the op raises out of the
            # codec. The arm catches it, reports it, and keeps its handle.
            await tab.notify("app.create", app_id="", name="", source="")
            # Same arm, a real event this time.
            await tab.notify("app.create", app_id="a_ok", name="ok", source=SRC)
            assert list(tab.rows()) == ["a_ok"]
            # And the other surface's arms are untouched by any of it.
            await tab.notify("app.rename", app_id="a_ok", name="still here")
            assert tab.rows()["a_ok"]["name"] == "still here"
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
