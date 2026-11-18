"""What every assembly shares about a space on disk: the data dir, how a space is found, its root.

A space is a directory, any one, its data kept in ``.nuspace/`` the way a
repository keeps ``.git/``::

    <space root>/
      .nuspace/
        host.lock                  the lock of the open holding the space
        store/space.db             Space
        store/state.db             State
        store/blobs/               Blobs, the blob store (LMDB, or files on a network disk)
        devices/web/web_state.db   Web, with the web device
        devices/web/conn.db        Conn, made fresh at every open
        devices/web/uploads/       files tabs posted, wiped at every open
        infra/valkey/              the notification server's dir, per open

The store files are the store records' (:mod:`nuspace.shapes.stores`,
:mod:`nuspace.web.stores`). The Space store's file is the mark of a
space: ``~/.nuspace`` holds the user's config whether or not home is a space.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from nuspace.shapes.stores import SPACE_STORE


if TYPE_CHECKING:
    import os


__all__ = [
    "DATA_DIR",
    "LOCK_FILE",
    "OLDER",
    "data_dir",
    "find_space",
    "is_older",
    "is_space",
    "resolve_root",
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


def resolve_root(path: str | os.PathLike[str] | None) -> tuple[str, bool]:
    """The space's root, absolute, and whether it is a throwaway one.

    None names a throwaway root in the temp dir: the assembly makes it and
    removes it at the end. Anything else is expanded and resolved.
    """
    if path is None:
        return str(Path(tempfile.gettempdir()) / f"nuspace-{uuid.uuid4().hex[:8]}"), True
    return str(Path(path).expanduser().resolve()), False
