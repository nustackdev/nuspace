"""The kernel's two terms: :func:`init`, once per space, and :func:`driver`, its whole life at every start.

:func:`init` makes what the kernel needs in the stores and keeps there: the
live indexes and the system planes. An assembly runs it when it inits a
space, after core's init (``nuspace.shapes.stores.init``). :func:`driver`,
from reap to close::

    reap                 what an earlier kernel started and left live, ended killed
    stamp                Space.info.opened_at, this kernel's start
    system.ensure()      the system planes, made where missing: init made
                         them already, and it is idempotent, so a plane
                         removed by hand or new in this nuspace comes back
    system.start()       init's plane run asked for, unless it has a live one
    loop                 one arm per live plane run, never returning
      finally close      what this kernel started and left live, ended interrupted

The stamp comes before anything runs: init and the supervisor read
``opened_at`` to tell a run of this kernel from an earlier one. Asks made
before the start (by nav, by an ``open``) are left pending by reap and
started by the loop.

It works on the shapes and on what it finds in context: the stores bound,
the worker pool, and :func:`~.kernel.bound` (backends, envs, space envs).
It names no file, path, backend of a store, or process: the assembly
around it brings all of them, its envs included.
"""

from __future__ import annotations

import nu
import nustd.kv
import nustd.time
from nuspace import system
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space

from .close import close
from .kernel import loop
from .live import init_live
from .reap import reap


__all__ = ["driver", "init"]


def init() -> nu.Nu:
    """The kernel's init: the live indexes' sets, one commit, then the system planes. Idempotent.

    Needs the stores bound and core's init run before it. Writes what is
    missing and leaves what is there; runs nothing.
    """
    return nustd.kv.atomic(init_live()) >> system.ensure()


def _stamp() -> nu.Nu:
    """``Space.info.opened_at``, now. One commit. Only the kernel writes it."""
    return atomic(Space.info.opened_at.set(nustd.time.time()))


def driver() -> nu.Nu:
    """The kernel, its whole life: reap, stamp, system planes, then the loop, ``finally`` close.

    Never returns. Needs the stores bound, the worker pool and
    :func:`~.kernel.bound` around it; makes none of them. Cancelled, the
    loop's arms drain first (each lets its workers go), then close ends
    what is still live, while the stores and the pool are still bound.
    """
    return (
        reap()
        >> _stamp()
        >> system.ensure()
        >> system.start()
        >> nu.TryCatch(loop(), finally_=close())
    )
