"""The kernel: the main driver. It runs plane runs and cell runs on workers, and records them.

The ops write what is wanted to ``Space.exec`` (``plane_run.add``,
``interrupt_at``, ``kill_at``); the kernel makes it true through the
backends, never asking which kind, and writes what happened through the
same ops. An assembly runs it as one term, :func:`driver`, inside what it
binds::

    stores, worker pool, bound(backends, envs, space_envs)
      driver()
        reap, stamp opened_at, system planes, loop, finally close

The kernel names no file, path or process: the stores, the pool and its
envs come from the assembly. Reap and close end only what a kernel
started; a plane run asked for and never started stays pending, and the
next kernel starts it.

- :mod:`.driver`: :func:`driver`, the kernel's whole life as one term.
- :mod:`.kernel`: the loop, one arm per live plane run, and :func:`bound`,
  what it needs around it.
- :mod:`.reap`: at start, what an earlier kernel started and left live,
  ended killed.
- :mod:`.close`: at a clean close, what this kernel started and left live,
  ended interrupted.
- :mod:`.live`: the live indexes' sets, made by whoever inits the stores.
- :mod:`.body`: one cell run's life on its worker.
- :mod:`.envs`: named env factories, resolved per cell run in the kernel.
- :mod:`.out`: a cell run's stdout and stderr, captured in the worker.
- :mod:`.records`: the guarded end writes the kernel, reap and close share.
- :mod:`.interactions`: the kernel's own nu interactions.
- :mod:`.backends`: what runs cells on workers: the contract, ``mp``, ``async``.
"""

from .backends import (
    BACKENDS,
    PER_CELL_RUN,
    PER_PLANE_RUN,
    AsyncBackend,
    Backend,
    MpBackend,
    PoolBackend,
    UnknownBackendError,
)
from .body import build_body
from .close import CLOSED, close
from .driver import driver
from .envs import Env, EnvFactory, KernelConfig, UnknownEnvError
from .kernel import ORPHAN, UNENDED, bound
from .live import init_live
from .reap import LEFT_OVER, reap


__all__ = [
    "BACKENDS",
    "CLOSED",
    "LEFT_OVER",
    "ORPHAN",
    "PER_CELL_RUN",
    "PER_PLANE_RUN",
    "UNENDED",
    "AsyncBackend",
    "Backend",
    "Env",
    "EnvFactory",
    "KernelConfig",
    "MpBackend",
    "PoolBackend",
    "UnknownBackendError",
    "UnknownEnvError",
    "bound",
    "build_body",
    "close",
    "driver",
    "init_live",
    "reap",
]
