"""The browser's terms: ``OpenTab``, the write, and ``Listening``, the look before it."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared

from .fabric import browser_of


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Listening", "OpenTab", "listening"]


class OpenTab(nu.Command):
    """A tab opened on ``url`` through the browser the ref in slot 0 reads.

    Args:
        ref: The browser, a ``BrowserRef``: :data:`~.refs.BROWSER`.
        url: What to open, a str or a term yielding one.

    Notes:
        - No browser bound, the system one opens it.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, ref: nu.Nu, url: nu.StrArg) -> None:
        super().__init__(ref, url)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref, url = children

        def thunk(rt: Runtime) -> None:
            browser_of(ref(rt)).open(str(url(rt)))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref, url = children

        async def athunk(rt: Runtime) -> None:
            # Handing a url over is sync and quick.
            browser_of(await ref(rt)).open(str(await url(rt)))

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
