"""The kernel: runs, interrupts and kills plane runs, runs and interrupts cell runs, records them.

Headless and in the host, where the backends are. The ops write intents to
the store (D1); the kernel reads them and makes them true through the
backends (:mod:`nuspace.system.backends`), never asking which kind:

- :mod:`.space`: the brackets a space opens in, and :func:`open_kernel`.
- :mod:`.envs`: named env factories, resolved per cell run in the host.
- :mod:`.body`: one cell run's life on its worker.
- :mod:`.out`: a cell run's stdout and stderr, captured per cell run.
- :mod:`.dispatch`: a cell run's body built and run by its backend, to its end.
- :mod:`.runs`: the fold over live plane runs.
- :mod:`.reconcile`: at open, leftovers ended killed.
- :mod:`.kernel`: all of it as one term.
"""

from .body import build_body, end_cell_run
from .dispatch import RunCell
from .envs import Env, EnvFactory, KernelConfig, KernelConfigRef, UnknownEnvError
from .kernel import INIT_BY, init_start, kernel, kernel_loop
from .out import OUT_CAP
from .reconcile import reconcile
from .runs import end_run, outcome, run_arm, run_fold
from .space import (
    DEFAULT_NAME,
    DEFAULT_SPARES,
    KERNEL_FILE,
    STATE_FILE,
    VALKEY_DIR,
    NotASpace,
    navigator,
    open_kernel,
    space_dir,
    store,
    worker_context,
    worker_pool,
)


__all__ = [
    "DEFAULT_NAME",
    "DEFAULT_SPARES",
    "INIT_BY",
    "KERNEL_FILE",
    "OUT_CAP",
    "STATE_FILE",
    "VALKEY_DIR",
    "Env",
    "EnvFactory",
    "KernelConfig",
    "KernelConfigRef",
    "NotASpace",
    "RunCell",
    "UnknownEnvError",
    "build_body",
    "end_cell_run",
    "end_run",
    "init_start",
    "kernel",
    "kernel_loop",
    "navigator",
    "open_kernel",
    "outcome",
    "reconcile",
    "run_arm",
    "run_fold",
    "space_dir",
    "store",
    "worker_context",
    "worker_pool",
]
