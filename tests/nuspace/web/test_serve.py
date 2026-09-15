"""The web transport, proved against a real uvicorn on a real socket.

One minimal Shell with one Screen is served, the server is booted through its
own lifecycle, and a browser-shaped websocket client reads the boot batch back
off the wire. No mocks, no TestClient: what the browser will do is what the
test does.
"""

from __future__ import annotations

import asyncio

import pytest
import websockets

import nu
import nustd.ui
from nuspace.apps import free_port
from nuspace.web import NuspaceServer, Screen, Shell, server
from nustd.ui.core.protocol import OP_INIT, OP_REMOVE, decode


class Home(Screen):
    """One screen with two output refs, enough to fill a boot batch."""

    title = nustd.ui.HeadingRef.slot(label="nuspace")
    body = nustd.ui.TextRef.slot(value="hello")


class Demo(Shell):
    """The smallest shell that still has chrome and a screen."""

    heading = nustd.ui.HeadingRef.slot(label="demo")
    home = Home.slot("/home")


#: Body long enough that the connection outlives the boot read. The eval task
#: racing the intake task is what would otherwise close the ws immediately.
IDLE = nu.Delay(30.0)


async def _get(port: int, path: str) -> bytes:
    """One HTTP/1.1 GET over raw streams.

    Everything here shares the test's event loop with uvicorn, so a blocking
    client (``urllib``) would deadlock rather than talk to the server.
    """
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n".encode())
    await writer.drain()
    body = await reader.read()
    writer.close()
    await writer.wait_closed()
    return body


def test_the_boot_batch_is_one_chain_per_slot_in_declaration_order():
    """A screen is a level, so its refs start at the slot it was declared at."""
    chains = Demo._boot_chains()
    assert [[seg for seg, _, _ in chain] for chain in chains] == [
        ["heading"],
        ["home"],
        ["home", "title"],
        ["home", "body"],
    ]
    assert chains[0] == (("heading", "HeadingRef", {"label": "demo"}),)
    # The screen's own level draws as a Column and carries its route.
    assert chains[1] == (("home", "Column", {"route": "/home"}),)
    assert chains[2][-1] == (
        "title",
        "HeadingRef",
        {"label": "nuspace", "level": 1, "align": "left"},
    )


async def test_the_server_boots_and_the_ws_delivers_the_boot_batch():
    port = free_port()
    fabric = NuspaceServer(
        IDLE,
        shell_cls=Demo,
        host="127.0.0.1",
        port=port,
        open_browser=False,
    )
    await fabric.asetup(nu.Context())
    try:
        index = await asyncio.wait_for(_get(port, "/"), timeout=5)
        async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
            frames = [
                decode(await asyncio.wait_for(ws.recv(), timeout=5))
                for _ in range(len(Demo._boot_chains()) + 1)
            ]
    finally:
        await fabric.acleanup()

    assert index.startswith(b"HTTP/1.1 200 OK")
    assert b'<div id="root"></div>' in index
    # The clearing remove first, then one init per slot, chain and all.
    assert frames[0].op == OP_REMOVE
    assert [f.op for f in frames[1:]] == [OP_INIT] * len(Demo._boot_chains())
    assert [f.chain for f in frames[1:]] == [tuple(c) for c in Demo._boot_chains()]
    assert frames[2].ref == ("home",)


async def test_the_provide_bracket_opens_and_closes_the_port():
    """``server()`` boots and tears down inside a plain ``nu.With``."""
    port = free_port()
    tree = nu.With(
        server(IDLE, shell_cls=Demo, host="127.0.0.1", port=port, open_browser=False),
        body=nu.Delay(0.05),
    )
    await nu.arun(tree, nu.Context())
    with pytest.raises(OSError):
        await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout=5)
