"""The workers' context: what every worker comes up holding, built from the same bindings as its parent.

A worker binds the same stores, on the same backends and notifier, as the
process that spawned it, so a cell run reads and writes what everybody
else does. The assembly hands in its bindings, the very term it opens its
own stores with, so no worker rebuilds them its own way. The pool gets
this context pickled and enters it in the child.

What a worker needs of its parent's run, eg the space's root, is no term
the worker could run: it is a value of the parent's. So the pool takes its
init as a query, run where the pool opens, yielding the bracket the
workers enter, the parent's values in it as plain values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.mp

from .resources import Warmed


if TYPE_CHECKING:
    from nu.context import Provide


__all__ = ["DEFAULT_GRACE", "DEFAULT_NAME", "DEFAULT_SPARES", "worker_context", "worker_pool"]


#: Process name prefix for the pool's workers, so a space shows in a process list.
DEFAULT_NAME = "nuspace"

#: How many idle workers the pool keeps up: one for the plane being opened,
#: one for the tab beside it.
DEFAULT_SPARES = 2

#: Seconds a worker gets to end once let go, or when the space closes: torn
#: down politely, killed past it.
DEFAULT_GRACE = 2.0


def worker_context(bindings: nu.Nu, blobs: Provide) -> nu.With:
    """What every worker comes up holding. Pickled to the child, entered there.

    Process scope only, since the pool pays it on every launch: the stores
    as the assembly binds them, the blob store and the warm module cache.
    Whatever one run needs rides in its body, its mem shapes in frames of
    their own.

    Args:
        bindings: Every store bound to its navigators, the same term the
            assembly opens its own stores with. Must pickle.
        blobs: The blob store's spec (``nuspace.Blobs``).
    """
    return nu.With(bindings, blobs, nu.Provide(Warmed, kwargs={}))


def worker_pool(
    init: nu.Nu,
    *,
    name: str = DEFAULT_NAME,
    spares: int = DEFAULT_SPARES,
    grace: float = DEFAULT_GRACE,
) -> nu.Provide:
    """The fleet, every worker holding what ``init`` yields. Closing stops them all.

    ``nustd.mp.pool`` quotes its init, a bracket fixed when the tree is
    built; this is its ``Provide`` with the init computed where the pool
    opens instead.

    Args:
        init: A query yielding the bracket every worker enters, eg a
            ``nu.Literal(factory=...)`` building :func:`worker_context`
            from the run's values. It must pickle.
        name: Process name prefix.
        spares: Idle workers to keep up, so a launch does not wait for a spawn.
        grace: Seconds a worker gets to end, polite first, killed past it.
    """
    options = {"init": init, "name": name, "spares": spares, "grace": grace}
    return nu.Provide(nustd.mp.WorkerPool, kwargs=options)
