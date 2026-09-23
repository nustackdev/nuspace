"""The kernel term: reconcile, then the worker fold and pid 1.

Everything the kernel does is in the host, reading records the ops wrote
(D1) and making them true. Nothing else starts cells.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import plane_exists, up_plane, worker
from nuspace.shapes import Space

from .reconcile import reconcile
from .workers import orphans, worker_fold


__all__ = ["INIT_BY", "init_start", "kernel", "kernel_loop"]


#: What runs the kernel starts are recorded as ``by``.
INIT_BY = "kernel"

_INIT_WORKER = "nuspace.kernel.init_worker"


def init_start(plane_id: str) -> nu.Nu:
    """Bring ``plane_id`` up on a fresh worker, if the plane exists. pid 1."""
    return nu.IfDo(
        nustd.kv.Snapshot(plane_exists(plane_id), scope=Space),
        nu.Let(
            _INIT_WORKER,
            worker(),
            up_plane(plane_id, worker=nu.StrAttrRef(_INIT_WORKER), by=INIT_BY),
        ),
    )


def kernel_loop(init: str | None = None) -> nu.Nu:
    """The worker fold, the orphan sweep, and ``init`` brought up beside them.

    Assumes reconciled. Never returns.
    """
    arms = [worker_fold(), orphans()]
    if init is not None:
        arms.append(init_start(init))
    return nu.ParallelAsync(*arms)


def kernel(init: str | None = None) -> nu.Nu:
    """The whole kernel: reconcile, then :func:`kernel_loop`. Never returns.

    Needs the brackets of :func:`~.space.open_kernel` around it: the store,
    the pool, spares, and a :class:`~.envs.KernelConfig`.

    Args:
        init: a plane to bring up once reconciled. Skipped if it does not exist.
    """
    return reconcile() >> kernel_loop(init)
