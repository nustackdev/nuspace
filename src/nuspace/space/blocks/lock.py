"""A driver's lock: one of each driver runs on a space at a time.

An assembly takes one lock per driver it runs, a file it names (local:
``kernel/kernel.lock``, ``devices/web/web.lock``), first, before the
notification server and the stores, held until the driver stops. A POSIX
record lock (``fcntl.lockf``), which NFS carries across machines, so red
and blue never run two kernels of one space on the shared grid. The file
says who holds it, ``host pid taken_at``, read back when the lock is
refused and told with what it guards: ``the kernel of this space runs on
red, pid 1234``.

Best effort: a file system that cannot lock at all goes on with a warning.
A lock held by a live process refuses. A process that died frees the lock
with it, so the next one takes it, and reap ends what a dead kernel left
live. On NFSv4 a holder on a machine that died frees it only once its
lease runs out (about 90 s); until then it is refused.

A POSIX lock is the process's, so a second take in the same process would
succeed: the paths held here are kept in a set and refused too.
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


__all__ = ["Lock", "LockWarning", "held", "holder"]


#: Errors a non blocking lock raises when somebody else holds it.
_HELD = frozenset({errno.EACCES, errno.EAGAIN})

#: The lock files this process holds, by absolute path.
_MINE: set[str] = set()


class LockWarning(UserWarning):
    """A lock could not be taken for a reason other than another process holding it."""


def holder(path: str) -> str:
    """Who the lock file says holds it, ``host pid taken_at``, or ``""`` when it says nothing."""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def held(path: str) -> bool:
    """Whether a process holds the lock on ``path`` now. A look, nothing taken.

    This process's own locks are answered from the set: a second descriptor
    on the file, closed, would drop the lock this process holds on it.
    """
    if path in _MINE:
        return True
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError:
        return False
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        return exc.errno in _HELD
    else:
        fcntl.lockf(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _told(record: str) -> str:
    """A holder record as a refusal tells it: ``on <host>, pid <pid>``."""
    host, _, rest = record.partition(" ")
    pid = rest.partition(" ")[0]
    if not pid:
        return "in a process that left no record"
    return f"on {host}, pid {pid}"


class Lock:
    """The lock on ``path`` guarding ``what``, taken at setup, released at cleanup.

    Args:
        path: The lock file, absolute, in the space's data dir.
        what: What it guards, as a refusal names it: ``"kernel"``, ``"web"``.

    Raises:
        Refused: Another process, or another bracket in this one, holds it.
    """

    def __init__(self, path: str, what: str) -> None:
        self.path = path
        self.what = what
        self._fd: int | None = None

    def setup(self, ctx: Context) -> None:
        """Take the lock without waiting, and write who holds it."""
        if self.path in _MINE:
            msg = f"the {self.what} of this space runs in this process already, pid {os.getpid()}"
            raise Refused(msg)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in _HELD:
                msg = f"the {self.what} of this space runs {_told(holder(self.path))}. Stop it there first"
                raise Refused(msg) from None
            warnings.warn(
                f"could not take the {self.what} lock {self.path} ({exc}), going on without it",
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
