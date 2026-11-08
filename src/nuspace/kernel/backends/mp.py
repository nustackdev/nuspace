"""The ``mp`` backend: one worker per cell run, ending with it.

Every cell run gets a pool process of its own and lets it go once it is
over. A crash ends only that cell run: its siblings are other processes,
and the plane run goes on while any of them runs.
"""

from __future__ import annotations

from .base import PER_CELL_RUN
from .pool import PoolBackend


__all__ = ["NAME", "MpBackend"]


#: The name it is registered under.
NAME = "mp"


class MpBackend(PoolBackend):
    """One pool process per cell run."""

    placement = PER_CELL_RUN
