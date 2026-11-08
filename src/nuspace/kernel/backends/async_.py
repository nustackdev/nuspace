"""The ``async`` backend: one worker per plane run, every cell run a task in it.

The plane run takes one pool process before its first cell run, every cell
run runs in it (``mp_pool`` runs each request as its own asyncio task
there), and the plane run's end lets it go. The cells share one process:
cheap, and one cell crashing the process takes its siblings with it.
"""

from __future__ import annotations

from .base import PER_PLANE_RUN
from .pool import PoolBackend


__all__ = ["NAME", "AsyncBackend"]


#: The name it is registered under.
NAME = "async"


class AsyncBackend(PoolBackend):
    """One pool process per plane run, shared by all of its cell runs."""

    placement = PER_PLANE_RUN
