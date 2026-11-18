"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another. One
process owns it and the others publish to it. Which process that is, is
the assembly's call; local's is infra's, a process of its own, so the
server outlives a kernel that crashes.

- :func:`served`: the server started and owned for the body. It goes with
  its owner: nustd's keeper stops it when that process ends, however it ends.
- :class:`Heard`: one of two trees run, by whether the server answers as it
  starts. For a process that may run without one: with no server up
  nobody listens, so it binds stores that publish nothing.
- :func:`answers`, :data:`Answers`: whether the server answers now, plain
  and as a query. An entry point that needs the server checks it through
  :func:`~.required.required`.

The socket lives in ``/tmp`` of the machine, so a server serves one machine.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.valkey
from nustd.valkey.resources import ping, socket_path_for


if TYPE_CHECKING:
    import os
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Answers", "Heard", "answers", "served"]


#: How long one ping waits for an answer.
PING = 0.5


def answers(path: str | os.PathLike[str]) -> bool:
    """Whether the server of the dir ``path`` answers a ping now."""
    return ping(socket_path_for(Path(path)), PING)


#: ``Answers(path)``: :func:`answers` as a query, asked when the term runs.
Answers = nu.host(answers)


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


class Heard(nu.Bracket):
    """``served`` run when ``cond`` holds as this starts, else ``unserved``. Yields what the one run yields.

    The choice is made once, at start. Each tree is the same body under
    bindings of the same roots, one publishing to the server and one
    publishing nothing, so the body never tells them apart.

    Args:
        served: The body under the bindings that publish to the server,
            eg ``nu.With(stores, body=body)``.
        unserved: The same body under the bindings that publish nothing.
        cond: Whether the server answers, eg ``Answers(path)``.
    """

    def __init__(self, served: nu.Nu, unserved: nu.Nu, cond: nu.Nu) -> None:
        super().__init__(served, unserved, cond)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        served, unserved, cond = children

        def thunk(rt: Runtime) -> object:
            return served(rt) if cond(rt) else unserved(rt)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        served, unserved, cond = children

        async def athunk(rt: Runtime) -> object:
            return await (served if await cond(rt) else unserved)(rt)

        return athunk
