"""The blocks: shared parts every assembly is built from. None of them knows a driver.

- :mod:`.meta`: the data dir, ``meta.json``, how a space is found, root resolving.
- :mod:`.lock`: a POSIX record lock named for what it guards.
- :mod:`.notifier`: the notification server every process reaches, owned or joined.
- :mod:`.logs`: this process's logging pointed at a file.
- :mod:`.navigators`: a store's root bound to kv navigators, any backend.
- :mod:`.workers`: what every worker comes up holding, and the pool.
- :mod:`.resources`: the throwaway root, the data dir, warm imports.
- :mod:`.browse`: a browser tab opened once a server answers.
"""

from . import navigators
from .browse import Browse, BrowserRef
from .lock import Lock, LockWarning
from .logs import Logged, logs
from .meta import (
    DATA_DIR,
    META_FILE,
    Meta,
    data_dir,
    find_space,
    is_space,
    read_meta,
    resolve_root,
    stamp,
    write_meta,
)
from .notifier import Notifier, notifier
from .resources import DataDir, Throwaway, Warmed
from .workers import worker_context, worker_pool


__all__ = [
    "DATA_DIR",
    "META_FILE",
    "Browse",
    "BrowserRef",
    "DataDir",
    "Lock",
    "LockWarning",
    "Logged",
    "Meta",
    "Notifier",
    "Throwaway",
    "Warmed",
    "data_dir",
    "find_space",
    "is_space",
    "logs",
    "navigators",
    "notifier",
    "read_meta",
    "resolve_root",
    "stamp",
    "worker_context",
    "worker_pool",
    "write_meta",
]
