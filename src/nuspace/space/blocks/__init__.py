"""The blocks: shared parts every assembly is built from. None of them knows a driver.

- :mod:`.meta`: the data dir, ``meta.json`` read and written through an fs mount, how a space is found, root resolving.
- :mod:`.guarded`: steps before a body, its value kept; the refusal step.
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
from .guarded import Guarded, refused
from .logs import Logged, logged_to
from .meta import (
    DATA_DIR,
    META_FILE,
    Meta,
    data_dir,
    find_space,
    init_done,
    is_space,
    meta_in,
    other_refusal,
    read_meta,
    resolve_root,
    set_init,
    stamp,
)
from .notifier import Answers, answers, served
from .required import required
from .resources import Throwaway, Warmed, throwaway
from .workers import worker_context, worker_pool


__all__ = [
    "BROWSER",
    "DATA_DIR",
    "META_FILE",
    "Answers",
    "BrowserBackend",
    "BrowserRef",
    "Guarded",
    "Listening",
    "Logged",
    "Meta",
    "OpenTab",
    "Throwaway",
    "Warmed",
    "answers",
    "data_dir",
    "find_space",
    "init_done",
    "is_space",
    "logged_to",
    "meta_in",
    "navigators",
    "other_refusal",
    "read_meta",
    "refused",
    "required",
    "resolve_root",
    "served",
    "set_init",
    "stamp",
    "tab_opened",
    "throwaway",
    "worker_context",
    "worker_pool",
]
