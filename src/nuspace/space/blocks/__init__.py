"""The blocks: shared parts every assembly is built from. None of them knows a driver.

- :mod:`.meta`: the data dir, how a space is found, root resolving.
- :mod:`.lock`: a POSIX record lock named for what it guards.
- :mod:`.notifier`: the notification server every process reaches.
- :mod:`.navigators`: stores bound to kv navigators.
- :mod:`.workers`: what every worker comes up holding, and the pool.
- :mod:`.resources`: the throwaway root, the data dir, fresh files, warm imports.
- :mod:`.browse`: a browser tab opened once a server answers.
"""

from .browse import Browse, BrowserRef
from .lock import Lock, LockWarning
from .meta import DATA_DIR, data_dir, find_space, is_space, resolve_root
from .navigators import navigators
from .notifier import VALKEY_DIR, notifier
from .resources import DataDir, Fresh, Throwaway, Warmed
from .workers import worker_context, worker_pool


__all__ = [
    "DATA_DIR",
    "VALKEY_DIR",
    "Browse",
    "BrowserRef",
    "DataDir",
    "Fresh",
    "Lock",
    "LockWarning",
    "Throwaway",
    "Warmed",
    "data_dir",
    "find_space",
    "is_space",
    "navigators",
    "notifier",
    "resolve_root",
    "worker_context",
    "worker_pool",
]
