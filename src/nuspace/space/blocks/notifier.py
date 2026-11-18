"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another. One
process owns it and the others publish to it. Which process that is, is
the assembly's call; local's is infra's, a process of its own, so the
server outlives a kernel that crashes.

- :func:`served`: the server started and owned for the body. It goes with
  its owner: nustd's keeper stops it when that process ends, however it ends.
- :class:`Heard`: one of two bindings entered, by whether the server answers
  as the bracket opens. For a process that may run without one: with no
  server up nobody listens, so it binds stores that publish nothing.
- :func:`answers`: whether the server answers now. An entry point that
  needs the server checks it through :class:`~.required.Required`.

The socket lives in ``/tmp`` of the machine, so a server serves one machine.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import nustd.valkey
from nu.core.spans.bracket import _LifecycleBracket
from nustd.valkey.resources import ping, socket_path_for


if TYPE_CHECKING:
    import os
    from collections.abc import AsyncIterator, Iterator

    import nu
    from nu.lang.runtime import Context


__all__ = ["Heard", "answers", "served"]


#: How long one ping waits for an answer.
PING = 0.5


def answers(path: str | os.PathLike[str]) -> bool:
    """Whether the server of the dir ``path`` answers a ping now."""
    return ping(socket_path_for(Path(path)), PING)


def served(path: str | os.PathLike[str]) -> nu.Provide:
    """The server of the dir ``path`` started for the body and stopped at its end. The owner's.

    Put before the navigators in a ``nu.With``: the server answers before
    their publishers connect, and stops after they close. Its url is
    ``nustd.valkey.url_for(path)``, which every other process and every
    worker build on their own.

    Args:
        path: The server's dir, absolute.
    """
    return nustd.valkey.server(Path(path).resolve())


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
