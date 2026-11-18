"""The notifier: the one Valkey server a space's stores send their change notifications through.

Every process on a space reaches the same server at a unix socket derived
from its dir, so a write in one process wakes a watch in another. Which
dir is the assembly's call. Several processes need it at once (a kernel,
a web, an ``open``), started in any order and stopped in any order, so
none of them may assume it is the server's only user:

- **Own or join.** A process pings first. If the server answers it joins;
  if nobody answers it starts the server itself and owns it. A start lock
  in the dir (``start.lock``, ``fcntl.lockf``) makes the ping and the start
  one step, so two processes coming up together never start two servers.
- **Holders.** Each bracket on the server writes a holder file in the dir,
  ``held.<host>.<pid>.<n>``, and drops it when it closes.
- **Last out stops it.** A bracket closing, under the start lock, drops its
  holder file, prunes the files of dead pids on this host, and stops the
  server only when no holder is left: the owner by its keeper, anyone else
  by ``SHUTDOWN`` on the socket. An owner leaving first leaves the server
  up for the others, so no server is pulled from under a joiner.

nustd's ``ValkeyServer`` has no handover, so the owner starts it with its
watchdog off: the server outlives its owner. A server left by processes
that all crashed answers the next ping, is joined, and is stopped at the
next clean last exit. The socket lives in ``/tmp`` of the machine, so a
server serves one machine: holders are pruned per host.
"""

from __future__ import annotations

import contextlib
import fcntl
import itertools
import os
import socket
import time
from pathlib import Path
from typing import TYPE_CHECKING

import nu
from nustd.valkey.resources import ValkeyServer, ping, socket_path_for


if TYPE_CHECKING:
    from collections.abc import Iterator

    from nu.lang.runtime import Context


__all__ = ["Notifier", "holders", "notifier"]


#: The lock that makes ping and start one step, in the server's dir.
START_LOCK = "start.lock"

#: The prefix of a holder file, ``held.<host>.<pid>.<n>``.
HELD = "held."

#: The shutdown command, as nustd sends it.
_SHUTDOWN = b"*2\r\n$8\r\nSHUTDOWN\r\n$6\r\nNOSAVE\r\n"

#: How long a stop waits for the server to stop answering.
_GONE_WITHIN = 5.0

#: Holder files of this process, numbered so two brackets in one process differ.
_COUNT = itertools.count()


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def holders(path: str | os.PathLike[str]) -> list[str]:
    """The holder files in the server's dir ``path``, by name, live or not."""
    try:
        return sorted(p.name for p in Path(path).iterdir() if p.name.startswith(HELD))
    except FileNotFoundError:
        return []


@contextlib.contextmanager
def _started(path: Path) -> Iterator[None]:
    """The dir's start lock, held for the block: waits while another process starts or stops."""
    fd = os.open(path / START_LOCK, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.lockf(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


class Notifier:
    """The space's notification server, owned or joined at setup, stopped by the last out.

    Args:
        path: The server's dir, absolute.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._server: ValkeyServer | None = None
        self._held: Path | None = None

    @property
    def owned(self) -> bool:
        """Whether this bracket started the server."""
        return self._server is not None

    def setup(self, ctx: Context) -> None:
        """Join the server answering on the dir's socket, or start it and own it."""
        here = Path(self.path)
        here.mkdir(parents=True, exist_ok=True)
        sock = socket_path_for(here)
        with _started(here):
            if not ping(sock, 0.5):
                server = ValkeyServer(data_dir=here, watchdog=False)
                server.setup(ctx)
                self._server = server
            held = here / f"{HELD}{socket.gethostname()}.{os.getpid()}.{next(_COUNT)}"
            held.write_text(f"{os.getpid()}\n", encoding="utf-8")
            self._held = held

    async def asetup(self, ctx: Context) -> None:
        """Async shim: a ping, and a start of a few milliseconds when nobody answers."""
        self.setup(ctx)

    def cleanup(self) -> None:
        """Let go of the server: stop it when no other holder is left, else leave it up."""
        held, self._held = self._held, None
        server, self._server = self._server, None
        if held is None:
            return
        here = Path(self.path)
        with _started(here):
            held.unlink(missing_ok=True)
            if self._others(here):
                if server is not None:
                    _let_go(server)
                return
            if server is not None and server.pid is not None:
                server.cleanup()
            else:
                _shut_down(socket_path_for(here))

    async def acleanup(self) -> None:
        """Async shim, no await points: a stop half done never leaves a server without holders."""
        self.cleanup()

    @staticmethod
    def _others(here: Path) -> bool:
        """Whether a live holder is left, the files of dead pids on this host pruned on the way."""
        me = socket.gethostname()
        left = False
        for name in holders(here):
            host, _, rest = name.removeprefix(HELD).rpartition(".")[0].rpartition(".")
            try:
                pid = int(rest)
            except ValueError:
                continue
            if host == me and not _alive(pid):
                (here / name).unlink(missing_ok=True)
                continue
            left = True
        return left


def _let_go(server: ValkeyServer) -> None:
    """The owner leaving first: its end of the keeper's pipe closed, the server left running.

    With the watchdog off the keeper ignores the pipe closing, so the
    server stays up for the holders left. nustd has no call for this.
    """
    fd, server._keeper_fd = server._keeper_fd, None
    if fd is not None:
        with contextlib.suppress(OSError):
            os.close(fd)


def _shut_down(sock: str) -> None:
    """Stop a server this bracket did not start: ``SHUTDOWN`` on its socket, then wait until it is gone."""
    with contextlib.suppress(OSError), socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        s.connect(sock)
        s.sendall(_SHUTDOWN)
        with contextlib.suppress(OSError):
            s.recv(64)
    deadline = time.monotonic() + _GONE_WITHIN
    while time.monotonic() < deadline and ping(sock, 0.1):
        time.sleep(0.01)


def notifier(path: str | os.PathLike[str]) -> nu.Provide:
    """The space's notification server, own or join (:class:`Notifier`), on a unix socket.

    Put before the navigators in a ``nu.With``: the server answers before
    their publishers connect, and is let go after they close. Its url is
    ``nustd.valkey.url_for(path)``, which a worker builds on its own.

    Args:
        path: The server's dir, absolute.
    """
    return nu.Provide(Notifier, {"path": str(Path(path).resolve())})
