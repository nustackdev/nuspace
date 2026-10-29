"""The kernel term: reconcile, then the run fold and pid 1.

Everything the kernel does is in the host, reading the intents the ops
wrote (D1) and making them true through the backends. Nothing else runs
cells.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import plane_exists, plane_run
from nuspace.shapes import Space

from .reconcile import reconcile
from .runs import run_fold


__all__ = ["INIT_BY", "init_start", "kernel", "kernel_loop"]


#: What plane runs the kernel starts are recorded as ``by``.
INIT_BY = "kernel"


def init_start(plane_id: str) -> nu.Nu:
    """Run ``plane_id``, if the plane exists. pid 1."""
    return nu.IfDo(
        nustd.kv.Snapshot(plane_exists(plane_id), scope=Space), plane_run(plane_id, by=INIT_BY)
    )


def kernel_loop(init: str | None = None) -> nu.Nu:
    """The run fold, and ``init`` run beside it.

    Assumes reconciled. Never returns.
    """
    arms = [run_fold()]
    if init is not None:
        arms.append(init_start(init))
    return nu.ParallelAsync(*arms)


def kernel(init: str | None = None) -> nu.Nu:
    """The whole kernel: reconcile, then :func:`kernel_loop`. Never returns.

    Needs the brackets of :func:`~.space.open_kernel` around it: the store,
    the pool, spares, the backends, and a :class:`~.envs.KernelConfig`.

    Args:
        init: A plane to run once reconciled. Skipped if it does not exist.
    """
    return reconcile() >> kernel_loop(init)
