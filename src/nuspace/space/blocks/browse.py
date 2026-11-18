"""Browse: a browser tab opened on a url once the web server answers, as a term.

Opening a tab is a write to the browser, so it goes through a Ref like any
write (``nu.Print`` through ``STDOUT`` is the model): :data:`BROWSER`, in
slot 0 of :class:`OpenTab`. Waiting for the server is flow, a look every
tenth of a second under a timeout (:func:`tab_opened`).

- :class:`BrowserBackend`: what opens the url, the system browser unless a
  test binds its own on the Context, so no test ever launches one.
- :class:`BrowserRef`, :data:`BROWSER`: the Ref. Its read yields the
  backend, its write opens a url.
- :class:`OpenTab`: open a url now.
- :data:`Listening`: whether a server takes connections at ``host:port``.
- :func:`tab_opened`: open a url once a server takes connections, or give up
  quietly.
"""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING, cast

import nu
from nu.engine.structure import Declared


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Context, Runtime


__all__ = [
    "BROWSER",
    "BrowserBackend",
    "BrowserRef",
    "Listening",
    "OpenTab",
    "listening",
    "tab_opened",
]


#: How often :func:`tab_opened` looks for the server.
EVERY = 0.1


class BrowserBackend:
    """What opens a url: the system browser. Bind a subclass on the Context to redirect it."""

    def open(self, url: str) -> None:
        """Open ``url`` in a tab."""
        webbrowser.open(url)


#: The system browser, when the Context binds no backend.
SYSTEM = BrowserBackend()


def browser_of(ctx: Context) -> BrowserBackend:
    """The backend bound on ``ctx``, else the system browser."""
    return ctx.fabrics.get(BrowserBackend) if ctx.fabrics.has(BrowserBackend) else SYSTEM


class BrowserRef(nu.Ref):
    """The Ref naming the browser, what :class:`OpenTab` writes. One: :data:`BROWSER`.

    Yields:
        The :class:`BrowserBackend` in effect.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> BrowserBackend:
            return browser_of(rt.ctx)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> BrowserBackend:
            return browser_of(rt.ctx)

        return athunk

    def _write(self, rt: Runtime, value: str, nid: int) -> None:
        """Open the url ``value``: the fabric's WRITE half."""
        browser_of(rt.ctx).open(value)

    async def _awrite(self, rt: Runtime, value: str, nid: int) -> None:
        """Async sibling of :meth:`_write`: handing a url over is sync work."""
        browser_of(rt.ctx).open(value)


#: The browser.
BROWSER = BrowserRef()


class OpenTab(nu.Command):
    """A tab opened on ``url`` through the browser Ref in slot 0.

    Args:
        ref: The browser, :data:`BROWSER`.
        url: What to open, a str term.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, ref: BrowserRef, url: nu.StrArg) -> None:
        super().__init__(ref, url)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = cast("BrowserRef", self._children[0])
        url = children[1]

        def thunk(rt: Runtime) -> None:
            ref._write(rt, str(url(rt)), rt.program.children[nid][0])

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = cast("BrowserRef", self._children[0])
        url = children[1]

        async def athunk(rt: Runtime) -> None:
            await ref._awrite(rt, str(await url(rt)), rt.program.children[nid][0])

        return athunk


async def listening(host: str, port: int) -> bool:
    """Whether ``host:port`` takes a connection now. A wildcard bind is reached on loopback."""
    host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host  # noqa: S104
    try:
        _, writer = await asyncio.open_connection(host, port)
    except OSError:
        return False
    writer.close()
    return True


#: ``Listening(host, port)``: :func:`listening` as a query, asked when the term runs. Async only.
Listening = nu.host(listening)


def tab_opened(url: nu.StrArg, host: str, port: int, timeout: float = 30.0) -> nu.Nu:
    """A tab opened on ``url`` once ``host:port`` takes a connection. Async only.

    For a body that runs beside the web device, which may not be up yet.
    Gives up quietly after ``timeout`` seconds.

    Args:
        url: What to open, a str term read once the server answers.
        host: Where the server binds.
        port: The port it binds.
        timeout: Seconds to wait for it.
    """
    down = nu.Not(Listening(host, port))
    waited = nu.Timeout(timeout, nu.WhileDo(down, nu.Delay(EVERY)), on_timeout=nu.Noop())
    return waited >> nu.IfDo(Listening(host, port), OpenTab(BROWSER, url))
