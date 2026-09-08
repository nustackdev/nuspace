"""``WorkerHandle`` -- the server-side end of one worker process.

Owns the child process, its socket, and the kill ladder. The ladder is
the whole reason sections are processes:

    graceful request -> bounded wait
    -> SIGTERM       -> bounded wait
    -> SIGKILL       -> bounded wait

In-process, cancellation is cooperative forever: a section spinning in a
tight loop or inside a C call can be asked to stop and simply will not.
Out of process, teardown is bounded and the bound is a number we choose.
A supervisor that cannot guarantee teardown is not a supervisor.
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .protocol import MSG_READY, MSG_STOP, connect_channel, socketpair


if TYPE_CHECKING:
    import socket
    from collections.abc import Mapping

    from .protocol import Channel


__all__ = ["Timeouts", "WorkerHandle"]


@dataclass(frozen=True)
class Timeouts:
    """Bounds for every wait the supervisor performs.

    ``graceful`` is how long a worker gets to unwind its own tree after a
    stop request. ``term`` and ``kill`` bound each signal step. The worst
    case for any single worker is their sum, and it is paid off the
    navigation path.
    """

    ready: float = 20.0
    graceful: float = 0.5
    term: float = 0.5
    kill: float = 2.0


class WorkerHandle:
    """One warm-or-running worker process."""

    def __init__(
        self,
        proc: asyncio.subprocess.Process,
        channel: Channel,
        sock: socket.socket,
    ) -> None:
        self._proc = proc
        self._channel = channel
        self._sock = sock
        self._stderr: deque[str] = deque(maxlen=40)
        self._stderr_task: asyncio.Task | None = None
        if proc.stderr is not None:
            self._stderr_task = asyncio.create_task(self._drain_stderr(proc.stderr))

    # -- construction --------------------------------------------------------

    @classmethod
    async def spawn(cls, *, timeouts: Timeouts | None = None) -> WorkerHandle:
        """Start a worker and wait for its ``ready``.

        The child inherits one end of an ``AF_UNIX`` socketpair by fd
        number. Nothing is pickled across the boundary, so there is no
        start-method or fork-safety question to answer.
        """
        bounds = timeouts or Timeouts()
        parent_sock, child_sock = socketpair()
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "nuspace.exec.worker",
                "--fd",
                str(child_sock.fileno()),
                pass_fds=(child_sock.fileno(),),
                stdin=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except BaseException:
            parent_sock.close()
            child_sock.close()
            raise
        child_sock.close()

        channel = await connect_channel(parent_sock)
        handle = cls(proc, channel, parent_sock)
        try:
            msg = await asyncio.wait_for(channel.recv(), timeout=bounds.ready)
        except (TimeoutError, asyncio.TimeoutError):
            await handle.stop(bounds)
            raise TimeoutError(f"worker did not report ready in {bounds.ready}s") from None
        if msg is None or msg.get("t") != MSG_READY:
            await handle.stop(bounds)
            raise RuntimeError(f"worker handshake failed: {msg!r} {handle.stderr_tail()}")
        return handle

    # -- accessors -----------------------------------------------------------

    @property
    def pid(self) -> int:
        """Child pid."""
        return self._proc.pid

    @property
    def alive(self) -> bool:
        """True until the child has been reaped."""
        return self._proc.returncode is None

    @property
    def returncode(self) -> int | None:
        """Exit status, or None while running."""
        return self._proc.returncode

    def stderr_tail(self) -> str:
        """Last lines the worker wrote to stderr, for error reporting."""
        return "\n".join(self._stderr).strip()

    # -- messaging -----------------------------------------------------------

    async def send(self, msg: Mapping[str, Any]) -> None:
        """Ship one control message down."""
        await self._channel.send(msg)

    async def recv(self) -> dict[str, Any] | None:
        """Next message from the worker, or None at EOF."""
        return await self._channel.recv()

    # -- teardown ------------------------------------------------------------

    async def stop(self, timeouts: Timeouts | None = None) -> str:
        """Run the kill ladder. Returns how the worker actually died.

        One of ``"already"``, ``"graceful"``, ``"term"``, ``"kill"`` or
        ``"leaked"``. ``"leaked"`` means SIGKILL was sent and the process
        still had not been reaped inside the bound, which on a sane
        kernel means uninterruptible io; the supervisor has already
        forgotten it either way.
        """
        bounds = timeouts or Timeouts()
        if not self.alive:
            await self._cleanup()
            return "already"

        with contextlib.suppress(Exception):
            await self._channel.send({"t": MSG_STOP})
        if await self._wait(bounds.graceful):
            await self._cleanup()
            return "graceful"

        with contextlib.suppress(ProcessLookupError):
            self._proc.terminate()
        if await self._wait(bounds.term):
            await self._cleanup()
            return "term"

        with contextlib.suppress(ProcessLookupError):
            self._proc.kill()
        if await self._wait(bounds.kill):
            await self._cleanup()
            return "kill"

        await self._cleanup()
        return "leaked"

    async def _wait(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(asyncio.shield(self._proc.wait()), timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            return False
        return True

    async def _cleanup(self) -> None:
        if self._stderr_task is not None:
            self._stderr_task.cancel()
            self._stderr_task = None
        await self._channel.aclose()
        with contextlib.suppress(OSError):
            self._sock.close()

    async def _drain_stderr(self, stream: asyncio.StreamReader) -> None:
        with contextlib.suppress(Exception):
            while True:
                line = await stream.readline()
                if not line:
                    return
                self._stderr.append(line.decode("utf-8", "replace").rstrip())

    def __repr__(self) -> str:
        return f"WorkerHandle(pid={self._proc.pid}, alive={self.alive})"
