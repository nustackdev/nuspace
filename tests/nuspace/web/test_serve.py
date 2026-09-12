"""The web transport, proved against a real uvicorn on a real socket.

One minimal Shell with one Screen is mounted, the server is booted through
its own lifecycle, and a browser-shaped websocket client reads the mount
envelope back off the wire. No mocks, no TestClient: what the browser will
do is what the test does.
"""

from __future__ import annotations

import asyncio

import pytest
import websockets

import nu
import nu.ui
from nu.ui.core.protocol import OP_MOUNT, decode
from nuspace.apps import free_port
from nuspace.web import NuspaceServer, Screen, Screens, Shell, server


class Home(Screen):
    """One screen with one output ref, enough to fill a fields list."""

    title = nu.ui.HeadingRef.slot(label="nuspace")
    body = nu.ui.TextRef.slot(value="hello")


class Demo(Shell):
    """The smallest shell that still has chrome and a screen."""

    heading = nu.ui.HeadingRef.slot(label="demo")
    screens = Screens({"/home": Home})


#: Body long enough that the connection outlives the mount read. The eval task
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


def test_the_mount_payload_keeps_the_wire_keys():
    """Python says Screen/Screens; the wire still says ``pages``."""
    payload = Demo._mount_payload()
    assert set(payload) == {"name", "fields", "pages"}
    assert payload["name"] == "Demo"
    assert [f["path"] for f in payload["fields"]] == ["heading"]
    (page,) = payload["pages"]
    assert page == {
        "route": "/home",
        "name": "Home",
        "label": "home",
        "fields": [
            {
                "path": "Home.title",
                "type": "HeadingRef",
                "props": {"label": "nuspace", "level": 1, "align": "left"},
            },
            {"path": "Home.body", "type": "TextRef", "props": {"value": "hello"}},
        ],
    }


async def test_the_server_boots_and_the_ws_delivers_the_mount():
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
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
        frame = decode(raw)
    finally:
        await fabric.acleanup()

    assert index.startswith(b"HTTP/1.1 200 OK")
    assert b'<div id="root"></div>' in index
    assert frame.op == OP_MOUNT
    assert frame.payload == Demo._mount_payload()


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
