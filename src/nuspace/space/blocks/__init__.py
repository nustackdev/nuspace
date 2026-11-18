"""The blocks: shared parts every assembly is built from. None of them knows a driver.

- :mod:`.meta`: the data dir, ``meta.json``, how a space is found, root resolving.
- :mod:`.lock`: a POSIX record lock named for what it guards.
- :mod:`.notifier`: the notification server: owned by one process, published to by the rest.
- :mod:`.required`: what an entry point needs running, checked at its start, or a refusal.
- :mod:`.logs`: this process's logging pointed at a file.
- :mod:`.navigators`: a store's root bound to kv navigators, any backend.
- :mod:`.workers`: what every worker comes up holding, and the pool.
- :mod:`.resources`: the throwaway root, the data dir, warm imports.
- :mod:`.browse`: a browser tab opened once a server answers.
"""

from . import navigators
from .browse import Browse, BrowserRef
from .lock import Lock, LockWarning, held
from .logs import Logged, logged_to
from .meta import (
    DATA_DIR,
    META_FILE,
    Meta,
    data_dir,
    find_space,
    is_space,
    read_meta,
    resolve_root,
    set_init,
    stamp,
    write_meta,
)
from .notifier import Heard, answers, served
from .required import Required
from .resources import DataDir, Throwaway, Warmed
from .workers import worker_context, worker_pool


__all__ = [
    "DATA_DIR",
    "META_FILE",
    "Browse",
    "BrowserRef",
    "DataDir",
    "Heard",
    "Lock",
    "LockWarning",
    "Logged",
    "Meta",
    "Required",
    "Throwaway",
    "Warmed",
    "answers",
    "data_dir",
    "find_space",
    "held",
    "is_space",
    "logged_to",
    "navigators",
    "read_meta",
    "resolve_root",
    "served",
    "set_init",
    "stamp",
    "worker_context",
    "worker_pool",
    "write_meta",
]
