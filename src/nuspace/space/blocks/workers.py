"""The workers' context: what every worker comes up holding, built from the same bindings as its parent.

A worker binds the same stores, on the same files and server, as the
process that spawned it, so a cell run reads and writes what everybody
else does. The pool gets this context pickled and enters it in the child.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.mp_pool

from .navigators import navigators
from .resources import Warmed


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.context.fabric import Provide
    from nuspace.shapes import Store


__all__ = ["DEFAULT_GRACE", "DEFAULT_NAME", "DEFAULT_SPARES", "worker_context", "worker_pool"]


#: Process name prefix for the pool's workers, so a space shows in a process list.
DEFAULT_NAME = "nuspace"

#: How many idle workers the pool keeps up: one for the plane being opened,
#: one for the tab beside it.
DEFAULT_SPARES = 2

#: Seconds a worker gets to end once let go, or when the space closes: torn
#: down politely, killed past it.
DEFAULT_GRACE = 2.0


def worker_context(data: str, stores: Sequence[Store], blobs: Provide) -> nu.With:
    """What every worker comes up holding. Pickled to the child, entered there.

    Process scope only, since the pool pays it on every launch: every store
    of the open, opened by the worker itself on its parent's files and server,
    the blob store, a dict for process local records, and the warm module
    cache. Whatever one run needs rides in its body.

    Args:
        data: The space's data dir, absolute.
        stores: The stores of the open, core ones and the devices'.
        blobs: The blob store's spec (``nuspace.Blobs``).
    """
    return nu.With(navigators(data, stores), blobs, nu.Provide(dict, {}), nu.Provide(Warmed, {}))


def worker_pool(
    data: str,
    stores: Sequence[Store],
    blobs: Provide,
    *,
    name: str = DEFAULT_NAME,
    spares: int = DEFAULT_SPARES,
    grace: float = DEFAULT_GRACE,
) -> nu.Provide:
    """The fleet, every worker holding :func:`worker_context`. Closing stops them all.

    Args:
        data: The space's data dir, absolute.
        stores: The stores every worker binds.
        blobs: The blob store's spec every worker binds.
        name: Process name prefix.
        spares: Idle workers to keep up, so a launch does not wait for a spawn.
        grace: Seconds a worker gets to end, polite first, killed past it.
    """
    return nustd.mp_pool.pool(
        name=name, init=worker_context(data, stores, blobs), spares=spares, grace=grace
    )
