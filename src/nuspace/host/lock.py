"""The host lock: one host holds a space open at a time.

``.nuspace/host.lock``, taken first at open, before the notification server
and the stores, held until the space closes. A POSIX record lock
(``fcntl.lockf``), which NFS carries across machines, so red and blue never
open one space on the shared grid together. The file says who holds it,
``host pid opened_at``, read back when the lock is refused and told as
``open on <host>, pid <pid>``.

Best effort: a file system that cannot lock at all opens with a warning.
A lock held by a live host refuses the open. A host that died frees the
lock with its process, so the next open takes it, and reap ends what the
dead host left live. On NFSv4 a holder on a machine that died frees it
only once its lease runs out (about 90 s); until then the open is refused.

A POSIX lock is the process's, so a second open in the same process would
take it again: the paths held here are kept in a set and refused too.
"""

from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import socket
import time
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

from nuspace.errors import Refused


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = ["HostLock", "LockWarning", "holder"]


#: Errors a non blocking lock raises when somebody else holds it.
_HELD = frozenset({errno.EACCES, errno.EAGAIN})

#: The lock files this process holds, by absolute path.
_MINE: set[str] = set()


class LockWarning(UserWarning):
    """The host lock could not be taken for a reason other than another host holding it."""


def holder(path: str) -> str:
    """Who the lock file says holds it, ``host pid opened_at``, or ``""`` when it says nothing."""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _told(record: str) -> str:
    """A holder record as a refusal tells it: ``open on <host>, pid <pid>``."""
    host, _, rest = record.partition(" ")
    pid = rest.partition(" ")[0]
    if not pid:
        return "open in a host that left no record"
    return f"open on {host}, pid {pid}"


class HostLock:
    """The host lock on ``path``, taken at setup, released at cleanup.

    Args:
        path: The lock file, absolute, in the space's data dir.

    Raises:
        Refused: Another host, or another open in this process, holds it.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._fd: int | None = None

    def setup(self, ctx: Context) -> None:
        """Take the lock without waiting, and write who holds it."""
        if self.path in _MINE:
            msg = f"the space is open already in this process ({os.getpid()})"
            raise Refused(msg)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in _HELD:
                msg = f"the space is {_told(holder(self.path))}. Close it there first"
                raise Refused(msg) from None
            warnings.warn(
                f"could not take the host lock {self.path} ({exc}), opening without it",
                LockWarning,
                stacklevel=2,
            )
            return
        self._fd = fd
        _MINE.add(self.path)
        os.ftruncate(fd, 0)
        os.write(fd, f"{socket.gethostname()} {os.getpid()} {time.time():.3f}\n".encode())

    async def asetup(self, ctx: Context) -> None:
        """Async shim: the lock is taken without waiting."""
        self.setup(ctx)

    def cleanup(self) -> None:
        """Release the lock. The file stays, naming the last holder."""
        fd, self._fd = self._fd, None
        if fd is None:
            return
        _MINE.discard(self.path)
        with contextlib.suppress(OSError):
            fcntl.lockf(fd, fcntl.LOCK_UN)
        os.close(fd)
