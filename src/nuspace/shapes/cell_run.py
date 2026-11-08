"""CellRun: one run of a cell inside a plane run."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["OUT_CAP", "CellRun"]


#: How many output lines a cell run keeps: past it the oldest drop.
OUT_CAP = 200


class CellRun(nu.Shape):
    """One cell run's row at ``Space.exec.cell_runs[id]``. Flat: one id addresses it.

    ``plane_run`` is the plane run it belongs to, ``cell`` the cell it runs,
    ``version`` the cell's version when it was asked for, so a run of an
    older prog is told apart without reading source. ``by`` says who asked.
    ``worker`` is the worker its backend put it on.

    ``out`` is its output, ``[ts, stream, text]`` entries in a ring that
    keeps the last :data:`OUT_CAP`. One writer: the run itself.

    Lifecycle: ``created_at`` and ``interrupt_at`` are asked for by ops;
    ``started_at``, ``ended_at``, ``exit`` (one of
    :data:`~nuspace.shapes.exec.EXITS`) and ``error`` are observed by the
    kernel.
    """

    plane_run = nustd.kv.StrRef.slot()
    cell = nustd.kv.StrRef.slot()
    version = nustd.kv.IntRef.slot()
    by = nustd.kv.StrRef.slot()
    worker = nustd.kv.StrRef.slot()
    exit = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()
    out = nustd.kv.RingRef.slot(list, capacity=OUT_CAP)
    created_at = nustd.kv.FloatRef.slot()
    started_at = nustd.kv.FloatRef.slot()
    interrupt_at = nustd.kv.FloatRef.slot()
    ended_at = nustd.kv.FloatRef.slot()
