"""Where a space keeps its data: the data dir inside the space's root, and how a space is found.

A space is a directory, any one, its data kept in ``.nuspace/`` the way a
repository keeps ``.git/``::

    <space root>/
      .nuspace/
        host.lock                  the host holding the space open
        store/space.db             Space
        store/state.db             State
        devices/web/web_state.db   Web, with the web device
        devices/web/conn.db        Conn, made fresh at every open
        infra/valkey/              the notification server's dir, per open

The store files are the store records' (:mod:`.stores`,
:mod:`nuspace.web.stores`). The Space store's file is the mark of a
space: ``~/.nuspace`` holds the user's config whether or not home is a space.
"""

from __future__ import annotations

from pathlib import Path

from .stores import SPACE_STORE


__all__ = [
    "DATA_DIR",
    "LOCK_FILE",
    "OLDER",
    "data_dir",
    "find_space",
    "is_older",
    "is_space",
]


#: The directory inside a space's root holding its data.
DATA_DIR = ".nuspace"

#: The host lock's file inside :data:`DATA_DIR`.
LOCK_FILE = "host.lock"

#: What a nuspace of an older store format kept, in :data:`DATA_DIR` or loose
#: in the root: its stores, or a RocksDB store's ``CURRENT``. Refused, no converter.
OLDER = ("kernel.sqlite", "state.sqlite", "CURRENT")


def data_dir(root: str | Path) -> Path:
    """The data dir of the space whose root is ``root``."""
    return Path(root) / DATA_DIR


def is_space(root: str | Path) -> bool:
    """Whether ``root`` is a space of this nuspace: its data dir holds a Space store."""
    return (data_dir(root) / SPACE_STORE.file).is_file()


def is_older(root: str | Path) -> bool:
    """Whether ``root`` holds a space of an older store format, and none of this one."""
    if is_space(root):
        return False
    return any((data_dir(root) / f).is_file() or (Path(root) / f).is_file() for f in OLDER)


def find_space(start: str | Path) -> Path | None:
    """The nearest space at or above ``start``, as ``git`` finds a repository. None when there is none."""
    here = Path(start).expanduser().resolve()
    return next((d for d in (here, *here.parents) if is_space(d)), None)
