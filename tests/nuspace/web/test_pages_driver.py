"""The pages surface, proved against a real server over a real websocket.

One process, one store, one uvicorn, ``websockets`` clients standing in for
browser tabs. Nothing is mocked and no driver function is called directly:
every write is a notify frame on that op's own wire path, and everything
asserted came back over the socket.

The loop the task names -- create a page, add sections, edit a snippet,
reorder, delete -- is driven once, in order. Then a **second connection**
opens, gets its own driver, and boots from the same store having seen none of
the traffic: that is the kv assertion, made through a path that could not
have cached anything. Both connections then watch the same delete land.

A client answers ``read`` frames the way the browser's store does, which is
what makes the route per view: the server keeps no copy of it and asks every
time it needs to know.
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
from nuspace.web import NavRef, PagesRef, Screen, Shell, pages_driver, server


class PagesScreen(Screen):
    """The one screen this suite serves."""

    pages = PagesRef.slot()


class Demo(Shell):
    """Shell with the two refs the driver is built out of."""

    nav = NavRef.slot()
    pages = PagesScreen.slot("/pages")


#: Where the chain puts ``Demo.pages.pages``: the screen slot, then the ref.
#: Asserted below, not assumed, and every op path is built from it.
REF = ("pages", "pages")

#: How long a client waits for the frames one op produces to stop arriving.
QUIET = 0.5


class Browser:
    """A websocket client behaving the way the real browser's store does.

    Answers ``read`` with its own route, keeps the last payload per write op,
    and collects every frame so a test can assert on traffic rather than only
    on end state.
    """

    def __init__(self, ws, page_id=ROOT_PAGE_ID):
        self.ws = ws
        self.route = {"top": "pages", "page_id": page_id}
        self.frames = []
        self.last = {}

    async def _take(self, timeout):
        frame = decode(await asyncio.wait_for(self.ws.recv(), timeout=timeout))
        if frame.op == OP_READ:
            # The browser owns the route; the server asks for it every time.
            await self.ws.send(
                encode(Frame(OP_READ, ref=frame.ref, payload=dict(self.route), id=frame.id))
            )
        elif frame.op == OP_WRITE:
            payload = frame.payload or {}
            self.last[str(payload.get("op"))] = payload
        self.frames.append(frame)
        return frame

    async def boot(self):
        """The opening batch: a clearing remove, then one init per slot."""
        frames = [await self._take(5.0) for _ in range(len(Demo._boot_chains()) + 1)]
        assert [f.op for f in frames[1:]] == [OP_INIT] * len(frames[1:])
        return [f.chain for f in frames[1:]]

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

    def goto(self, page_id):
        """Move this connection's route, the way clicking a rail row does."""
        self.route["page_id"] = page_id

    def tree(self):
        """The rail as ``{page_id: row}``, from the last ``set_tree``."""
        return {p["id"]: p for p in self.last["set_tree"]["pages"]}

    def blocks(self):
        """Block ids on the canvas, from the last ``set_page``."""
        return [b["id"] for b in self.last["set_page"]["blocks"]]


def _driver(_address):
    """A fresh driver per connection, which is what the ws endpoint wants.

    The endpoint hands over this connection's session address; the pages
    surface has nothing to dispatch, so it does not use it.
    """
    return pages_driver(Demo.pages.pages, Demo.nav)


def _space(port, body):
    """One store, one server, one body. Brackets tear down LIFO when it ends."""
    return nu.With(
        nu.kv.memory_navigator(tags=(Space,)),
        server(_driver, shell_cls=Demo, host="127.0.0.1", port=port, open_browser=False),
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


def test_the_driver_is_a_flat_fold_of_arms_and_nothing_else():
    """The thesis, pinned: N reactive arms, no dispatch, no python in an atom."""
    from nuspace.web.pages.driver import ARMS

    tree = _driver("127.0.0.1:0")
    nodes = list(_walk(tree))

    arms = [n for n in nodes if isinstance(n, nu.ReactForever)]
    assert len(arms) == ARMS

    # No branching on a kind. Guards (`IfDo`) are allowed and dispatch is not:
    # an IfDo asks whether a page is there, a Switch asks which op this is.
    assert not [n for n in nodes if isinstance(n, (nu.Switch, nu.SwitchDo))]

    # Nothing smuggles a python function into an atom's payload. Classes are
    # allowed: a Shape class is an address, not behaviour.
    for node in nodes:
        for value in (getattr(node, "_payload", None) or {}).values():
            assert isinstance(value, type) or not callable(value), (
                f"{type(node).__name__} carries {value!r}"
            )


@pytest.mark.timeout(180)
async def test_the_whole_page_loop_runs_over_one_websocket():
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
            chains = await tab.boot()
            await tab.settle()

            # The ref is where its chain says it is, which is what every op
            # path below is built from.
            paths = {tuple(seg for seg, _, _ in chain): chain[-1] for chain in chains}
            assert paths[REF][1] == "PagesRef"
            assert paths[("nav",)][1] == "NuspaceNavRef"
            # What a new block starts life as rides in the chain, so the
            # browser fills `source` on a create without owning a template.
            starters = paths[REF][2]["starters"]
            assert set(starters) == {"program", "text"}
            assert all(s.startswith("import nu") for s in starters.values())

            # A cold store boots itself: the root page is there before anyone
            # asked, and the rail was told so unprompted.
            assert list(tab.tree()) == [ROOT_PAGE_ID]

            # -- create a page --------------------------------------------------
            await tab.notify("page.create", page_id="p_notes", parent_id=ROOT_PAGE_ID, title="N")
            rows = tab.tree()
            assert set(rows) == {ROOT_PAGE_ID, "p_notes"}
            assert rows["p_notes"]["parent"] == ROOT_PAGE_ID
            assert rows[ROOT_PAGE_ID]["children"] == ["p_notes"]

            # -- go there, and be told what is there ----------------------------
            tab.goto("p_notes")
            await tab.notify("page.select", page_id="p_notes")
            assert tab.last["set_page"]["page_id"] == "p_notes"
            assert tab.last["set_page"]["title"] == "N"
            assert tab.last["set_page"]["blocks"] == []
            assert tab.last["set_status"]["statuses"] == []

            # -- add two sections -------------------------------------------------
            for sid, name, source in (("s_a", "A", "src-a"), ("s_b", "B", "src-b")):
                await tab.notify(
                    "section.create",
                    page_id="p_notes",
                    section_id=sid,
                    name=name,
                    tpl="program",
                    source=source,
                )
            blocks = tab.last["set_page"]["blocks"]
            assert [b["id"] for b in blocks] == ["s_a", "s_b"]
            assert [b["source"] for b in blocks] == ["src-a", "src-b"]
            assert [b["name"] for b in blocks] == ["A", "B"]
            assert [s["section_id"] for s in tab.last["set_status"]["statuses"]] == ["s_a", "s_b"]

            # -- edit one snippet --------------------------------------------------
            await tab.notify("section.update", page_id="p_notes", section_id="s_a", source="edited")
            assert [b["source"] for b in tab.last["set_page"]["blocks"]] == ["edited", "src-b"]

            # -- reorder -------------------------------------------------------------
            await tab.notify("section.reorder", page_id="p_notes", section_ids=["s_b", "s_a"])
            assert tab.blocks() == ["s_b", "s_a"]

            # -- rename ----------------------------------------------------------------
            await tab.notify("page.rename", page_id="p_notes", title="Notebook")
            assert tab.last["set_page"]["title"] == "Notebook"

            # -- delete a section ---------------------------------------------------------
            await tab.notify("section.delete", page_id="p_notes", section_id="s_b")
            assert tab.blocks() == ["s_a"]

            # -- a second page, reparented, and a section moved onto it ------------
            await tab.notify("page.create", page_id="p_arch", parent_id=ROOT_PAGE_ID, title="A")
            await tab.notify("page.move", page_id="p_arch", parent_id="p_notes", index=0)
            rows = tab.tree()
            assert rows["p_arch"]["parent"] == "p_notes"
            assert rows["p_notes"]["children"] == ["p_arch"]
            assert rows[ROOT_PAGE_ID]["children"] == ["p_notes"]

            await tab.notify(
                "section.move", page_id="p_notes", section_id="s_a", to_page_id="p_arch", index=0
            )
            assert tab.blocks() == []

            # -- a second tab, booting from the store, having seen none of this ----
            async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws2:
                other = Browser(ws2, page_id="p_arch")
                await other.boot()
                await other.settle()
                # Its own driver, its own route, and the store agrees with
                # everything the first tab was told.
                assert other.tree()["p_arch"]["parent"] == "p_notes"
                assert other.last["set_page"]["page_id"] == "p_arch"
                assert other.blocks() == ["s_a"]

                # -- delete the page, subtree and all, watched from both ------
                await tab.notify("page.delete", page_id="p_notes")
                await other.settle()
                assert list(tab.tree()) == [ROOT_PAGE_ID]
                assert list(other.tree()) == [ROOT_PAGE_ID]

            # Every op the surface has was exercised except the two the canvas
            # composes out of others; both write ops came back on the wire.
            assert {"set_tree", "set_page", "set_status"} <= set(tab.last)
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task


@pytest.mark.timeout(120)
async def test_the_bracket_closes_the_port_behind_the_driver():
    """A driver that never finishes still tears down with its bracket."""
    port = free_port()
    await nu.arun(_space(port, nu.Delay(0.05)), nu.Context(), max_parallel=64)
    with pytest.raises(OSError):
        await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=5)


@pytest.mark.timeout(120)
async def test_a_bad_event_leaves_every_other_arm_alive():
    """One arm's body raising must not end the composition, or close the ws."""
    port = free_port()
    task = asyncio.create_task(nu.arun(_space(port, nu.Delay(90.0)), nu.Context(), max_parallel=64))
    try:
        await _await_port(port)
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            tab = Browser(ws)
            await tab.boot()
            await tab.settle()

            # An empty page id is not a kv key, so the op raises out of the
            # codec. The arm catches it, reports it, and keeps its handle.
            await tab.notify("section.create", page_id="", section_id="s", name="", source="")
            # Same arm, a real event this time.
            await tab.notify("page.create", page_id="p_ok", parent_id=ROOT_PAGE_ID, title="ok")
            assert "p_ok" in tab.tree()
            await tab.notify(
                "section.create",
                page_id="p_ok",
                section_id="s_ok",
                name="ok",
                tpl="program",
                source="src",
            )
            tab.goto("p_ok")
            await tab.notify("page.select", page_id="p_ok")
            assert tab.blocks() == ["s_ok"]
    finally:
        task.cancel()
        with contextlib.suppress(BaseException):
            await task
