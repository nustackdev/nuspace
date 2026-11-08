"""The kernel: the main driver. It runs plane runs and cell runs on workers, and records them.

The ops write what is wanted to ``Space.exec`` (``plane_run.add``,
``interrupt_at``, ``kill_at``); the kernel makes it true through the
backends, never asking which kind, and writes what happened through the
same ops. Nobody calls it but the host, which opens a space as::

    stores, worker pool, bound(...)
      reap() >> race(kernel(), the rest)

- :mod:`.kernel`: the driver, one arm per live plane run, and
  :func:`bound`, what it needs around it.
- :mod:`.reap`: at open, what a gone host left live ended killed.
- :mod:`.body`: one cell run's life on its worker.
- :mod:`.envs`: named env factories, resolved per cell run in the host.
- :mod:`.out`: a cell run's stdout and stderr, captured in the worker.
- :mod:`.records`: the guarded end writes the kernel and reap share.
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
from .envs import Env, EnvFactory, KernelConfig, UnknownEnvError
from .kernel import ORPHAN, UNENDED, bound, kernel
from .reap import LEFT_OVER, reap


__all__ = [
    "BACKENDS",
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
    "kernel",
    "reap",
]
