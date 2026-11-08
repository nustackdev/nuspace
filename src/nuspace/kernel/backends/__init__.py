"""Backends: what runs cells on workers. Fabrics the kernel never looks inside.

A plane names its backend (``Plane.backend``), a plane run records it, and
the kernel reaches it by that name through
:class:`~.interactions.BackendRef`. A new backend is a
:class:`~.base.Backend` subclass registered by name at open, with no kernel
edit.

- :mod:`.base`: the contract, placement, worker id keyed methods.
- :mod:`.interactions`: the ref and the calls the kernel makes.
- :mod:`.pool`: what both process backends share over ``nustd.mp_pool``.
- :mod:`.async_`: ``async``, one worker per plane run.
- :mod:`.mp`: ``mp``, one worker per cell run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .async_ import AsyncBackend
from .base import (
    PER_CELL_RUN,
    PER_PLANE_RUN,
    PLACEMENTS,
    Backend,
    UnknownBackendError,
    require_backend,
)
from .interactions import BackendRef, Kill, Launch, Placement, Run, Stop
from .mp import MpBackend
from .pool import PoolBackend


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = [
    "BACKENDS",
    "PER_CELL_RUN",
    "PER_PLANE_RUN",
    "PLACEMENTS",
    "AsyncBackend",
    "Backend",
    "BackendRef",
    "Kill",
    "Launch",
    "MpBackend",
    "Placement",
    "PoolBackend",
    "Run",
    "Stop",
    "UnknownBackendError",
    "provided",
    "require_backend",
]


#: The backends every space registers, by name. Registered ones of the same
#: name replace these.
BACKENDS: dict[str, type[Backend]] = {"async": AsyncBackend, "mp": MpBackend}


def provided(backends: Mapping[str, type[Backend]] | None = None) -> nu.With:
    """Every backend bound on the context under its name: :data:`BACKENDS`, then ``backends``.

    Goes inside the pool, which the process backends take from.

    Args:
        backends: Backend classes by name, on top of the built in ones.

    Raises:
        ValueError: A backend declares a placement none of ``PLACEMENTS``.
    """
    merged = {**BACKENDS, **(backends or {})}
    for name, cls in merged.items():
        if cls.placement not in PLACEMENTS:
            msg = f"Backend {name!r} declares placement {cls.placement!r}, not one of {PLACEMENTS}"
            raise ValueError(msg)
    return nu.With(
        *(nu.Provide(cls, {}, tag=name, bind_as=Backend) for name, cls in merged.items())
    )
