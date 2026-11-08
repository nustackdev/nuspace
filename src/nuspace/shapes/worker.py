"""Worker: what a backend runs cells on."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Worker"]


class Worker(nu.Shape):
    """One worker's row at ``Space.exec.workers[id]``. Kept after it ends, like runs.

    The kernel mints the id; every backend method takes it. ``backend`` is
    the backend that runs it, ``plane_run`` the plane run it serves.
    ``handle`` is the backend's own dict for it (pid and pgid for a
    process, a container id for a container): opaque to everyone else, so
    nothing outside its backend reads it.

    Lifecycle: ``created_at`` by the add op; ``started_at`` (with
    ``handle``), ``ended_at``, ``exit`` (one of
    :data:`~nuspace.shapes.exec.EXITS`) and ``error`` observed. What is live
    is in ``Space.exec.indexes.live.workers``.
    """

    backend = nustd.kv.StrRef.slot()
    plane_run = nustd.kv.StrRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    handle = nustd.kv.PrimitiveDictRef.slot()
    created_at = nustd.kv.FloatRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    ended_at = nustd.kv.FloatRef.slot()
