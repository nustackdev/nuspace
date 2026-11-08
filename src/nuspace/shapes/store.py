"""Store: one store of a space, as a record: its root shape, its file, its channel, its init.

The core stores are declared in :mod:`nuspace.host.stores`, a device's
beside its shapes (the web device: :mod:`nuspace.devices.web.stores`). The
record sits here, with the roots, so the host and the devices both read it
and neither imports the other for it. A store has no ops of its own: its
init term is the one thing it runs, and the store's declaration builds it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu


__all__ = ["Store"]


@dataclass(frozen=True)
class Store:
    """One store of a space: its root shape, its file, its notify channel, its init.

    Attributes:
        root: The root shape, also the tag its navigator is bound under.
        file: The SQLite file, relative to the space's data dir.
        channel: The notify channel prefix, explicit, one per store.
        init: Builds the bare term that makes the store's fixed containers.
        fresh: Deleted and made again at every open: what it holds lives
            as long as one open of the space (the web device's tabs). Only
            a device's stores may set it: the host never deletes a core one.
    """

    root: type[nu.Shape]
    file: str
    channel: str
    init: Callable[[], nu.Nu]
    fresh: bool = False
