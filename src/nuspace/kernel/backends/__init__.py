"""Backends: what executes plane runs. Polymorphic fabrics the kernel never looks inside.

A plane names its backend (``props.backend``), a plane run records it, and
the kernel reaches it by that name through :class:`~.base.BackendRef`. A new
backend is a :class:`~.base.Backend` subclass registered by name at open,
with no kernel edit.

- :mod:`.base`: the fabric, its ref, its interactions, and the worker
  records every backend writes through them.
- :mod:`.pool`: the books both process backends keep over ``nustd.mp_pool``.
- :mod:`.async_`: ``async``, one worker per plane run.
- :mod:`.mp`: ``mp``, one worker per cell run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .async_ import AsyncBackend
from .base import (
    Backend,
    BackendRef,
    EndCell,
    KillRun,
    PlaceCell,
    StartRun,
    UnknownBackendError,
    end_cell,
    ended,
    kill,
    lost,
    placed,
    released,
    require_backend,
    start,
)
from .mp import MpBackend
from .pool import PoolBackend


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = [
    "BACKENDS",
    "AsyncBackend",
    "Backend",
    "BackendRef",
    "EndCell",
    "KillRun",
    "MpBackend",
    "PlaceCell",
    "PoolBackend",
    "StartRun",
    "UnknownBackendError",
    "end_cell",
    "ended",
    "kill",
    "lost",
    "placed",
    "provided",
    "released",
    "require_backend",
    "start",
]


#: The backends every space registers, by name. Registered ones of the same
#: name replace these.
BACKENDS: dict[str, type[Backend]] = {"async": AsyncBackend, "mp": MpBackend}


def provided(backends: Mapping[str, type[Backend]] | None = None) -> nu.With:
    """Every backend bound on the context under its name: :data:`BACKENDS`, then ``backends``.

    Goes inside the pool and its shelf, which the process backends take from.

    Args:
        backends: Backend classes by name, on top of the built in ones.
    """
    merged = {**BACKENDS, **(backends or {})}
    return nu.With(
        *(nu.Provide(cls, {}, tag=name, bind_as=Backend) for name, cls in merged.items())
    )
