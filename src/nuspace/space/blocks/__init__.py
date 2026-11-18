"""The blocks: shared parts every assembly is built from. None of them knows a driver.

- :mod:`.meta`: the data dir, ``meta.json`` (its Ref and Commands), how a space is found, root resolving.
- :mod:`.disk`: the disk as a fabric: its Ref and the Commands that write it.
- :mod:`.guarded`: steps before a body, its value kept; the refusal step.
- :mod:`.lock`: a POSIX record lock named for what it guards.
- :mod:`.notifier`: the notification server: owned by one process, published to by the rest.
- :mod:`.required`: what an entry point needs running, looked for at its start, or a refusal.
- :mod:`.logs`: this process's logging pointed at a file.
- :mod:`.navigators`: a store's root bound to kv navigators, any backend.
- :mod:`.workers`: what every worker comes up holding, and the pool.
- :mod:`.resources`: what a run holds: the throwaway root, warm imports.
- :mod:`.browse`: a browser tab opened once a server answers.
"""

from . import navigators
from .browse import BROWSER, BrowserBackend, BrowserRef, Listening, OpenTab, tab_opened
from .disk import DISK, DiskBackend, DiskRef, MakeDirs, RemoveIfHolds, RemoveTree, WriteWhole
from .guarded import Guarded, refused
from .lock import Held, Lock, LockWarning, held
from .logs import Logged, logged_to
from .meta import (
    DATA_DIR,
    META_FILE,
    InitDone,
    Meta,
    MetaRef,
    SetInit,
    Stamp,
    data_dir,
    data_made,
    find_space,
    init_done,
    is_space,
    read_meta,
    resolve_root,
    write_meta,
)
from .notifier import Answers, Heard, answers, served
from .required import required
from .resources import Throwaway, Warmed, throwaway
from .workers import worker_context, worker_pool


__all__ = [
    "BROWSER",
    "DATA_DIR",
    "DISK",
    "META_FILE",
    "Answers",
    "BrowserBackend",
    "BrowserRef",
    "DiskBackend",
    "DiskRef",
    "Guarded",
    "Heard",
    "Held",
    "InitDone",
    "Listening",
    "Lock",
    "LockWarning",
    "Logged",
    "MakeDirs",
    "Meta",
    "MetaRef",
    "OpenTab",
    "RemoveIfHolds",
    "RemoveTree",
    "SetInit",
    "Stamp",
    "Throwaway",
    "Warmed",
    "WriteWhole",
    "answers",
    "data_dir",
    "data_made",
    "find_space",
    "held",
    "init_done",
    "is_space",
    "logged_to",
    "navigators",
    "read_meta",
    "refused",
    "required",
    "resolve_root",
    "served",
    "tab_opened",
    "throwaway",
    "worker_context",
    "worker_pool",
    "write_meta",
]
