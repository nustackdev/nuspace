"""The host's own nu interactions: opening a browser tab once the web device answers.

- :class:`BrowserRef`: the browser, what :class:`Browse` writes. Nothing is bound.
- :class:`Browse`: open a url once a server takes connections.
"""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING

from nu.engine.structure import Declared
from nu.lang import Command, Ref


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu
    from nu.lang.runtime import Runtime


__all__ = ["Browse", "BrowserRef", "browse"]


async def browse(url: str, host: str, port: int, timeout: float = 30.0) -> None:
    """Open ``url`` in a browser once ``host:port`` takes a connection.

    For a body that runs beside the web device, which may not be up yet.
    Gives up quietly after ``timeout`` seconds.
    """
    # A wildcard bind is reached on loopback.
    host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host  # noqa: S104
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        try:
            _, writer = await asyncio.open_connection(host, port)
        except OSError:
            if loop.time() > deadline:
                return
            await asyncio.sleep(0.1)
            continue
        writer.close()
        break
    webbrowser.open(url)


class BrowserRef(Ref):
    """The Ref naming the browser, what :class:`Browse` writes. Nothing is bound.

    Declared so the engine keeps the open ordered and never folds it away
    as a pure read.

    Yields:
        None.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        return lambda rt: None

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> None:
            return None

        return athunk


class Browse(Command):
    """:func:`browse` as a term: the url read at run time, ``host:port`` fixed at build.

    Async only: a space is always run in a loop.

    Args:
        url: What to open, a str term.
        host: Where the server binds.
        port: The port it binds.
        timeout: Seconds to wait for it before giving up quietly.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, url: nu.StrArg, host: str, port: int, timeout: float = 30.0) -> None:
        super().__init__(BrowserRef(), url)
        self._payload = dict(self._payload)
        self._payload.update(host=host, port=port, timeout=timeout)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            msg = "Browse runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        _, url = children
        p = self._payload

        async def athunk(rt: Runtime) -> None:
            await browse(str(await url(rt)), p["host"], p["port"], p["timeout"])

        return athunk
