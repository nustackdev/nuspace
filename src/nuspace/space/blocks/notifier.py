"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nustd.valkey


if TYPE_CHECKING:
    import os

    import nu


__all__ = ["VALKEY_DIR", "notifier"]


#: The notification server's dir inside a space's data dir: ``infra/`` holds
#: what runs the space, not what it holds.
VALKEY_DIR = "infra/valkey"


def notifier(data: str | os.PathLike[str]) -> nu.Provide:
    """The space's notification server: one private Valkey for every store, on a unix socket.

    Put before the navigators in a ``nu.With``: the server answers before
    their publishers connect and stops after they close.

    Args:
        data: The space's data dir.
    """
    return nustd.valkey.server(Path(data) / VALKEY_DIR)
