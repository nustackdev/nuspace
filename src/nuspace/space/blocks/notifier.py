"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another. Which
dir is the assembly's call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nustd.valkey


if TYPE_CHECKING:
    import os

    import nu


__all__ = ["notifier"]


def notifier(path: str | os.PathLike[str]) -> nu.Provide:
    """The space's notification server: one private Valkey for every store, on a unix socket.

    Put before the navigators in a ``nu.With``: the server answers before
    their publishers connect and stops after they close. Its url is
    ``nustd.valkey.url_for(path)``, which a worker builds on its own.

    Args:
        path: The server's dir, absolute.
    """
    return nustd.valkey.server(path)
