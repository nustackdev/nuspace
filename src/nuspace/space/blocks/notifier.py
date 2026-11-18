"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another. One
process owns it and the others join it. Which process that is, is the
assembly's call; local's is the kernel's, since nothing on a space is
worth hearing while no kernel runs.

- :func:`served`: the server started and owned for the body. It goes with
  its owner: nustd's keeper stops it when that process ends, however it ends.
- :class:`Joined`: the server joined, after waiting a moment for it to come
  up, or a refusal saying what to start first.
- :class:`Heard`: one of two bindings entered, by whether the server answers
  as the bracket opens. For a process that may run without one: with no
  server up nobody listens, so it binds stores that publish nothing.
- :func:`answers`: whether the server answers now.

The socket lives in ``/tmp`` of the machine, so a server serves one machine.
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import nustd.valkey
from nu.core.spans.bracket import _LifecycleBracket
from nuspace.errors import Refused
from nustd.valkey.resources import ping, socket_path_for


if TYPE_CHECKING:
    import os
    from collections.abc import AsyncIterator, Callable, Iterator

    import nu
    from nu.lang.runtime import Context


__all__ = ["Heard", "Joined", "answers", "served"]


#: How long one ping waits for an answer.
_PING = 0.5

#: How often a join looks again while it waits.
_EVERY = 0.05


def answers(path: str | os.PathLike[str]) -> bool:
    """Whether the server of the dir ``path`` answers a ping now."""
    return ping(socket_path_for(Path(path)), _PING)


def served(path: str | os.PathLike[str]) -> nu.Provide:
    """The server of the dir ``path`` started for the body and stopped at its end. The owner's.

    Put before the navigators in a ``nu.With``: the server answers before
    their publishers connect, and stops after they close. Its url is
    ``nustd.valkey.url_for(path)``, which a joiner and a worker build on
    their own.

    Args:
        path: The server's dir, absolute.
    """
    return nustd.valkey.server(Path(path).resolve())


class Joined:
    """The server of the dir ``path`` joined: answering at setup, or within ``wait`` seconds while ``waiting()`` holds.

    Joining binds nothing: the navigators reach the server at its socket.
    It only makes sure there is one before they connect, and says what to
    start when there is none.

    Args:
        path: The server's dir, absolute.
        refusal: What a refusal says, eg ``"the kernel of this space is not
            running: start it first"``.
        wait: Seconds to wait for a server coming up.
        waiting: Whether one is coming up, asked at each look. None waits
            the whole ``wait``.

    Raises:
        Refused: No server answered.
    """

    def __init__(
        self,
        path: str,
        refusal: str,
        wait: float = 10.0,
        waiting: Callable[[], bool] | None = None,
    ) -> None:
        self.path = path
        self.refusal = refusal
        self.wait = wait
        self.waiting = waiting

    def _hold_on(self, deadline: float) -> bool:
        if time.monotonic() >= deadline:
            return False
        return self.waiting is None or self.waiting()

    def setup(self, ctx: Context) -> None:
        """Ping until the server answers, or refuse."""
        deadline = time.monotonic() + self.wait
        while not answers(self.path):
            if not self._hold_on(deadline):
                raise Refused(self.refusal)
            time.sleep(_EVERY)

    async def asetup(self, ctx: Context) -> None:
        """Ping until the server answers, or refuse, sleeping between looks on the loop."""
        deadline = time.monotonic() + self.wait
        while not answers(self.path):
            if not self._hold_on(deadline):
                raise Refused(self.refusal)
            await asyncio.sleep(_EVERY)


class Heard(_LifecycleBracket):
    """``served`` entered when the server of the dir ``path`` answers as this opens, else ``unserved``.

    The choice is made once, at open. Both are brackets binding the same
    roots, so the body never tells them apart.

    Args:
        path: The server's dir, absolute.
        served: The bindings that publish to the server.
        unserved: The bindings that publish nothing.
        body: What runs with the chosen one open.
    """

    def __init__(
        self,
        path: str,
        served: _LifecycleBracket,
        unserved: _LifecycleBracket,
        body: nu.Nu | None = None,
    ) -> None:
        super().__init__(body)
        self._payload.update(path=path, served=served, unserved=unserved)

    def _chosen(self) -> _LifecycleBracket:
        p = self._payload
        return p["served"] if answers(p["path"]) else p["unserved"]

    @contextmanager
    def _open(self, ctx: Context) -> Iterator[None]:
        with self._chosen()._open(ctx):
            yield

    @asynccontextmanager
    async def _aopen(self, ctx: Context) -> AsyncIterator[None]:
        async with self._chosen()._aopen(ctx):
            yield
