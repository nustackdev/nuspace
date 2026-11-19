"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another. One
process owns it and the others publish to it. Which process that is, is
the assembly's call; local's is infra's, a process of its own, so the
server outlives a kernel that crashes.

- :func:`served`: the server started and owned for the body. It goes with
  its owner: nustd's keeper stops it when that process ends, however it ends.
- :func:`answers`, :data:`Answers`: whether the server answers now, plain
  and as a query. A process that may run without one (``open``) branches
  on it with ``nu.IfDo``: with no server up nobody listens, so it binds
  stores that publish nothing. An entry point that needs the server checks it through
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


__all__ = ["Answers", "answers", "served"]


#: How long one ping waits for an answer.
PING = 0.5


def answers(path: str | os.PathLike[str]) -> bool:
    """Whether the server of the dir ``path`` answers a ping now."""
    return ping(socket_path_for(Path(path)), PING)


#: ``Answers(path)``: :func:`answers` as a query, asked when the term runs. A ping over
#: the server's socket, which nu has no op for: ``path`` may be a query too.
Answers = nu.host(answers)


def served(path: str | os.PathLike[str] | nu.Nu) -> nu.Provide:
    """The server of the dir ``path`` started for the body and stopped at its end. The owner's.

    Put before the navigators in a ``nu.With``: the server answers before
    their publishers connect, and stops after they close. Its url is
    ``nustd.valkey.url_for(path)``, which every other process and every
    worker build on their own.

    Args:
        path: The server's dir, absolute, or a query yielding it: read when
            the bracket opens.
    """
    return nustd.valkey.server(path)  # type: ignore[arg-type]  # a config child, a term is read at open
