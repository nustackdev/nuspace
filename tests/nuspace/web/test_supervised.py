"""The space with its supervisors attached, proved over a real websocket.

One process, one store, one uvicorn, ``websockets`` clients standing in for
browser tabs -- and, unlike the rest of the web suite, real worker processes
behind them. Nothing is mocked and no driver function is called directly:
every write is a notify frame on that op's own wire path.

What is asserted here is that things **run**. An app created through the
surface ticks a counter in kv and stops ticking when it is deleted; a section
created on the page a tab is looking at ticks its own counter, stops when
that tab navigates away, and starts again when it comes back. The counters
are read through the same Navigator the workers reach the store through,
because this process cannot open a store another process holds the lock on.
"""

from __future__ import annotations

import asyncio
import contextlib
import multiprocessing

import pytest
import websockets

import nu
import nustd.kv
import nustd.proxy
from nuspace.core.host import free_port
from nuspace.core.shapes import Space
from nuspace.pages import ROOT_PAGE_ID
from nuspace.web import NuspaceShell, session_driver, space_tree
from nustd.kv.fabrics import Navigator
from nustd.ui.core.protocol import OP_INIT, OP_NOTIFY, OP_READ, Frame, decode, encode


#: Where the chain puts the two surfaces: the screen slot, then the ref.
APPS = ("apps", "apps")
PAGES = ("pages", "pages")

#: The chrome a fresh connection is sent, one ``init`` per slot the shell
#: declares. What a tab reads before anything else arrives.
BOOT = NuspaceShell._boot_chains()

#: How long a client waits for the frames one op produces to stop arriving.
#: Shorter than the counters' period, so a ticking space still goes quiet.
QUIET = 0.4

#: And how long it is willing to wait in total. A running space never really
#: stops talking -- every tick is a kv change and every kv change is a status
#: frame -- so a settle that only watched for a gap could wait forever.
LIMIT = 20.0

#: How long to give a reconcile. It is a process spawn plus an interpreter
#: coming up and connecting back through the proxy, several times over for a
#: write that touches several fields.
SETTLE = 8.0

#: A section that counts, in its own row, forever. A section's snippet owns
#: its own atomicity; the runner does not add one.
COUNTER = """import nu
import nustd.kv
from nuspace.core.shapes import Space


def out(section):
    data = Space.state[section].data
    now = nu.ToInt(data.get_item("ticks", nu.Str("0")))
    tick = data.set_item("ticks", nu.ToStr(now + nu.Int(1)))
    return nustd.kv.auto_flow_atomic(
        data.set_item("ticks", nu.Str("0")) >> nu.ForeverDo(nu.DelayedDo(1.0, tick)),
        scope=Space,
    )
"""


class Tab:
    """A websocket client behaving the way the real browser's store does.

    Answers ``read`` with its own route -- which is how this test navigates --
    and keeps the last payload per ``(ref, op)`` so an assertion can name the
    surface it is about.
    """

    def __init__(self, ws, page_id=ROOT_PAGE_ID, top="pages"):
        self.ws = ws
        self.route = {"top": top, "page_id": page_id}
        self.last = {}

    async def _take(self, timeout):
        frame = decode(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
        if frame.op == OP_READ:
            await self.ws.send(
                encode(Frame(OP_READ, ref=frame.ref, payload=dict(self.route), id=frame.id))
            )
        elif frame.payload and "op" in frame.payload:
            self.last[frame.ref, str(frame.payload["op"])] = frame.payload
        return frame

    async def boot(self):
        """The opening batch: a clearing remove, then one init per slot.

        Comes back as ``{path: (segment, type, props)}`` -- the leaf of every
        chain, which is where a surface's declared props ride in.
        """
        frames = [await self._take(5.0) for _ in range(len(BOOT) + 1)]
        assert [f.op for f in frames[1:]] == [OP_INIT] * len(BOOT)
        chains = [f.chain for f in frames]
        assert chains[0] == ()
        return {tuple(seg for seg, _, _ in c): c[-1] for c in chains[1:]}

    async def arrive(self):
        """Say where this tab landed, the way the browser's route effect does.

        Nothing on the server reads the route unprompted, so a tab that never
        says it is on a page is a tab with nothing supervised.
        """
        await self.navigate(self.route["page_id"])

    async def settle(self, quiet=QUIET, limit=LIMIT):
        """Read until nothing has arrived for ``quiet`` seconds, or ``limit`` is up."""
        deadline = asyncio.get_running_loop().time() + limit
        while asyncio.get_running_loop().time() < deadline:
            try:
                await self._take(quiet)
            except TimeoutError:
                return

    async def notify(self, ref, op, **args):
        """Send one op on its own wire path, then let the answer settle."""
        # The op name stays one segment, dots and all.
        await self.ws.send(encode(Frame(OP_NOTIFY, ref=[*ref, "ops", op], payload=args)))
        await self.settle()

    async def navigate(self, page_id):
        """Move this tab, exactly the way the browser does it.

        The URL is the cursor, so the route moves first and the route effect
        ships ``page.select`` after it. Every arm that wants the route reads
        it back, and gets the new one.
        """
        self.route["page_id"] = page_id
        await self.notify(PAGES, "page.select", page_id=page_id)

    def apps(self):
        """The rail as ``{app_id: row}``, from the last ``set_apps``."""
        return {a["id"]: a for a in self.last[APPS, "set_apps"]["apps"]}

    def app_states(self):
        """What the last apps ``set_status`` said, as ``{app_id: state}``."""
        return {s["section_id"]: s["state"] for s in self.last[APPS, "set_status"]["statuses"]}

    def attached(self):
        """Whether the last ``set_apps`` said anything is supervising."""
        return self.last[APPS, "set_apps"]["attached"]

    def blocks(self):
        """The canvas as ``{section_id: block}``, from the last ``set_page``."""
        return {b["id"]: b for b in self.last[PAGES, "set_page"]["blocks"]}


def _tree(port, address, store=None):
    """The whole space in one process, with both supervisors attached."""
    return space_tree(
        store or nustd.kv.memory_navigator(tags=(Space,)),
        store_tag=Space,
        address=address,
        port=port,
        open_browser=False,
    )


async def _await_port(port, attempts=200):
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


async def ticks(address, owner):
    """One counter's current value, read the way a worker reads it.

    Through the served Navigator, because the tree under test holds the
    store's write lock and this process cannot open it a second time. ``-1``
    when that row has never been written, which is what "never ran" looks
    like.
    """
    cell = Space.state[owner].data.get_item("ticks", nu.Str("-1"))
    tree = nu.With(
        nustd.proxy.InvisiblesProxy(Navigator, address=address),
        body=nustd.kv.auto_flow_atomic(nu.ToStr(cell), scope=Space),
    )
    value, _ = await nu.arun(tree, nu.Context())
    return int(value)


async def advances(address, owner, over=2.5):
    """Whether a counter moves over a window. The proof that something runs."""
    before = await ticks(address, owner)
    await asyncio.sleep(over)
    return await ticks(address, owner) > before >= 0


@contextlib.asynccontextmanager
async def running_space(store=None):
    """The space, up and serving, with everything reaped on the way out."""
    port, address = free_port(), f"127.0.0.1:{free_port()}"
    task = asyncio.create_task(nu.arun(_tree(port, address, store), nu.Context(), max_parallel=64))
    try:
        try:
            await _await_port(port)
        except AssertionError:
            # The tree died on the way up. Its exception is the real failure.
            if task.done():
                task.result()
            raise
        yield port, address
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


# --- the composition -------------------------------------------------------


def _walk(term, seen=None):
    """Every Nu node in a tree, once."""
    seen = set() if seen is None else seen
    if id(term) in seen:
        return
    seen.add(id(term))
    yield term
    for child in getattr(term, "_children", ()) or ():
        yield from _walk(child, seen)


def test_the_session_driver_is_the_surfaces_plus_exactly_one_supervisor():
    """The per-connection tree is a fold, and the supervisor adds one loop."""
    from nu.lang import compile, validate
    from nuspace.web.apps.driver import ARMS as APPS_ARMS
    from nuspace.web.lens.driver import ARMS as LENS_ARMS
    from nuspace.web.pages.driver import ARMS as PAGES_ARMS

    tree = session_driver("127.0.0.1:0")
    nodes = list(_walk(tree))

    # Every arm of every driver, plus the supervisor's two: one on the browser
    # navigating, one on the store changing. Neither is ever rebuilt.
    assert len([n for n in nodes if isinstance(n, nu.ReactForever)]) == (
        APPS_ARMS + PAGES_ARMS + LENS_ARMS + 2
    )
    # No branching on a kind. Guards are allowed and dispatch is not.
    assert not [n for n in nodes if isinstance(n, (nu.Switch, nu.SwitchDo))]
    # Nothing smuggles a python function into an atom's payload. Classes are
    # allowed: a Shape class is an address, not behaviour.
    for node in nodes:
        for value in (getattr(node, "_payload", None) or {}).values():
            assert isinstance(value, type) or not callable(value), (
                f"{type(node).__name__} carries {value!r}"
            )
    # Parallel arms share one ``ctx.attrs``, so no two may bind one key.
    keys = [
        n._children[2]._payload["value"]
        for n in nodes
        if isinstance(n, nu.ReactForever) and n._payload["has_changed_key"]
    ]
    assert len(keys) == len(set(keys))

    validate(compile(tree))


# --- apps ------------------------------------------------------------------


@pytest.mark.timeout(300)
async def test_an_app_created_in_the_browser_actually_runs_and_says_so():
    """Create through the surface; the program runs, and the rail reads live."""
    async with running_space() as (port, address):
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Tab(ws, top="apps")
            slots = await tab.boot()
            await tab.settle()

            # The supervisor is in this process, and the surface read that
            # rather than being told it at build time.
            assert tab.attached() is True

            # What a new app starts life as, straight off the chain the
            # surface's own node arrived on: the browser fills `source` with
            # it, so this is the real create.
            starter = slots[APPS][2]["starter"]
            await tab.notify(APPS, "app.create", app_id="a_tick", name="Tick", source=starter)
            await asyncio.sleep(SETTLE)
            await tab.settle()

            assert list(tab.apps()) == ["a_tick"]
            # Live truth, off the supervisor's own bookkeeping, over the wire.
            assert tab.app_states()["a_tick"] == "running"
            # And the program is really executing: the starter is a 1 Hz
            # counter, and it is counting.
            assert await advances(address, "a_tick", over=2.5)

            # One worker, not the five a field-by-field create used to cost.
            assert len(multiprocessing.active_children()) == 1
            worker = multiprocessing.active_children()[0].pid

            # -- rename: metadata, so nothing restarts ---------------------
            await tab.notify(APPS, "app.rename", app_id="a_tick", name="Renamed")
            await asyncio.sleep(SETTLE)
            assert [p.pid for p in multiprocessing.active_children()] == [worker]

            # -- restart: a rewrite of the same source, and it still bites --
            await tab.notify(APPS, "app.restart", app_id="a_tick")
            await asyncio.sleep(SETTLE)
            assert len(multiprocessing.active_children()) == 1
            assert multiprocessing.active_children()[0].pid != worker

            # -- delete: the worker dies and the counter stops -------------
            await tab.notify(APPS, "app.delete", app_id="a_tick")
            await asyncio.sleep(SETTLE)
            await tab.settle()

            assert tab.apps() == {}
            assert not await advances(address, "a_tick", over=2.5)
            assert multiprocessing.active_children() == []


# --- pages -----------------------------------------------------------------


@pytest.mark.timeout(300)
async def test_a_section_runs_for_the_tab_that_is_looking_at_its_page():
    """The per-session supervisor follows the route, both ways."""
    key = "s_tick"
    async with running_space() as (port, address):
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Tab(ws)
            await tab.boot()
            await tab.settle()
            await tab.arrive()

            # A second page to navigate to, and a section on the first one.
            await tab.notify(PAGES, "page.create", page_id="p_other", parent_id=ROOT_PAGE_ID)
            await tab.notify(
                PAGES,
                "section.create",
                page_id=ROOT_PAGE_ID,
                section_id="s_tick",
                name="Tick",
                tpl="program",
                source=COUNTER,
                index=0,
            )
            await asyncio.sleep(SETTLE)
            await tab.settle()

            assert list(tab.blocks()) == ["s_tick"]
            # It is running, in a process of this connection's own.
            assert await advances(address, key)

            # -- navigate away: this page is not the one being looked at ---
            await tab.navigate("p_other")
            await asyncio.sleep(SETTLE)
            assert not await advances(address, key)

            # -- and back: it starts again ---------------------------------
            await tab.navigate(ROOT_PAGE_ID)
            await asyncio.sleep(SETTLE)
            assert await advances(address, key)

        # The socket is closed. The bracket owning this tab's worker records
        # unwinds and kills every one of them -- nothing else in the process
        # knew to, and the pool is shared so it cannot.
        await asyncio.sleep(SETTLE)
        assert multiprocessing.active_children() == []


@pytest.mark.timeout(300)
async def test_two_tabs_on_one_page_keep_their_own_records():
    """One tab closing must not take the other tab's section down with it."""
    key = "s_two"
    async with running_space() as (port, address):
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            first = Tab(ws)
            await first.boot()
            await first.settle()
            await first.arrive()
            await first.notify(
                PAGES,
                "section.create",
                page_id=ROOT_PAGE_ID,
                section_id="s_two",
                name="Tick",
                tpl="program",
                source=COUNTER,
                index=0,
            )
            await asyncio.sleep(SETTLE)

            async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as other:
                second = Tab(other)
                await second.boot()
                await second.settle()
                await second.arrive()
                await asyncio.sleep(SETTLE)
                # Each tab launched its own worker for the same section: a
                # page runs per view, and the two records live in two dicts.
                assert len(multiprocessing.active_children()) == 2

            # One tab left. The other's section is untouched.
            await asyncio.sleep(SETTLE)
            assert len(multiprocessing.active_children()) == 1
            assert await advances(address, key)

        await asyncio.sleep(SETTLE)
        assert multiprocessing.active_children() == []
