"""PlaneRun: one run of a plane."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["PlaneRun"]


class PlaneRun(nu.Shape):
    """One plane run's row at ``Space.exec.plane_runs[id]``. Its own facts only.

    ``plane`` is the plane it runs, ``backend`` that plane's backend when
    the run was asked for, ``by`` who asked. ``envs`` is the env specs its
    cells run inside, each ``[name, *args]`` naming a factory registered at
    open (``["session", sid]`` for a tab).

    Lifecycle, one slot per step. Asked for, written by ops:
    ``created_at`` (the record was added), ``interrupt_at`` (the last
    interrupt asked; the kernel interrupts live cell runs started before
    it), ``kill_at`` (when the run must be dead, the earliest wins).
    Observed, written by the kernel: ``started_at``, ``ended_at``, and how
    it ended, ``exit`` (one of :data:`~nuspace.shapes.exec.EXITS`) and
    ``error``.

    Lists live beside it, in ``Space.exec.indexes``: its cell runs and
    workers in ``history``, the live ones in ``live``.
    """

    plane = nustd.kv.StrRef.slot()
    backend = nustd.kv.StrRef.slot()
    by = nustd.kv.StrRef.slot()
    envs = nustd.kv.PrimitiveListRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    created_at = nustd.kv.FloatRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    interrupt_at = nustd.kv.FloatRef.slot()
    kill_at = nustd.kv.FloatRef.slot()
    ended_at = nustd.kv.FloatRef.slot()
