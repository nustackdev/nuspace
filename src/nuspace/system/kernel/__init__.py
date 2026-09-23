"""The kernel: starts, stops, records and reaps runs. Nothing else.

Headless and in the host, where the pool is. The ops write requests to the
store (D1); the kernel reads them and makes them true:

- :mod:`.space`: the brackets a space opens in, and :func:`open_kernel`.
- :mod:`.envs`: named env factories, resolved per run in the host.
- :mod:`.body`: one run's life in its worker.
- :mod:`.out`: a run's stdout and stderr, captured per run.
- :mod:`.dispatch`: a run's body built and shipped.
- :mod:`.workers`: the fold over living workers, and the orphan sweep.
- :mod:`.reconcile`: at open, leftovers marked dead.
- :mod:`.kernel`: all of it as one term.
"""

from .body import build_body
from .dispatch import DispatchRun
from .envs import Env, EnvFactory, KernelConfig, KernelConfigRef, UnknownEnvError
from .kernel import INIT_BY, init_start, kernel, kernel_loop
from .out import OUT_CAP
from .reconcile import reconcile
from .space import (
    DEFAULT_NAME,
    DEFAULT_SPARES,
    open_kernel,
    served_feed,
    served_navigator,
    store,
    worker_context,
    worker_pool,
)
from .workers import orphans, worker_fold


__all__ = [
    "DEFAULT_NAME",
    "DEFAULT_SPARES",
    "INIT_BY",
    "OUT_CAP",
    "DispatchRun",
    "Env",
    "EnvFactory",
    "KernelConfig",
    "KernelConfigRef",
    "UnknownEnvError",
    "build_body",
    "init_start",
    "kernel",
    "kernel_loop",
    "open_kernel",
    "orphans",
    "reconcile",
    "served_feed",
    "served_navigator",
    "store",
    "worker_context",
    "worker_fold",
    "worker_pool",
]
