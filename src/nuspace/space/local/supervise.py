"""local.run: the kernel and web as two child processes on one root, watched over.

Two processes so web can stop and start again (a crash, an extension
installed) while the kernel and every plane run it holds go on. They
share nothing in memory: the stores, the notifier and local's files are
all they meet through.

- **Start.** The kernel first, then web once the kernel's notification
  server answers (web joins it). Each is ``python -m
  nuspace.space.local.child kernel|web ROOT`` (:mod:`.child`), its
  options pickled on stdin, in a session of its own: a Ctrl+C on the
  terminal reaches only this process.
- **Ctrl+C**, or the term cancelled: web is stopped first (SIGINT, as a
  Ctrl+C), then the kernel, each given :data:`GRACE` seconds before SIGKILL.
- **Web dies**: started again, without opening a tab (the tab reconnects
  on its own). More than :data:`RESTARTS` times within :data:`WINDOW`
  seconds, or refused (a web runs elsewhere), and run stops, saying why.
- **The kernel exits**: web is stopped, and run ends with the kernel's
  status.
- **path None**: one throwaway root made here, both children use it, and
  it is removed once both are gone.

Each child's stdout and stderr are this process's: web's server says where
it listens, the kernel what it reaps. This process only says what it
does to them, on stderr, prefixed ``nuspace run:``.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import pickle
import signal
import subprocess
import sys
import time
from collections import deque
from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Command, Ref

from ..blocks.meta import data_dir, resolve_root
from ..blocks.notifier import answers
from ..blocks.resources import Throwaway
from . import binding
from .layout import WEB_LOG
from .plane import found


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from nu.lang.runtime import Runtime
    from nuspace.specs import PlaneSpec


__all__ = ["GRACE", "REFUSED", "RESTARTS", "WINDOW", "Restarts", "run"]


#: A child's exit status when its start was refused: run does not try again.
REFUSED = 2


#: How many web restarts run allows within :data:`WINDOW` seconds.
RESTARTS = 5
WINDOW = 60.0

#: Seconds a child gets to stop after SIGINT, before SIGKILL. The kernel's
#: close ends what is live and stops its workers in this time.
GRACE = 30.0

#: How often run looks at its children.
POLL = 0.1

#: Seconds run waits for the kernel's notification server before it gives up.
KERNEL_UP = 60.0

#: The options each entry point takes, so ``run`` hands each its own.
KERNEL = frozenset({"extensions", "envs", "space_envs", "backends", "spares", "name", "blobs"})
WEB = frozenset({"extensions", "host", "port", "static", "open_browser", "blobs"})


class Restarts:
    """Web's restarts within a sliding window: whether one more is allowed.

    Args:
        limit: Restarts allowed within ``window``.
        window: Seconds.
    """

    def __init__(self, limit: int = RESTARTS, window: float = WINDOW) -> None:
        self.limit = limit
        self.window = window
        self._at: deque[float] = deque()

    def allow(self, now: float) -> bool:
        """Whether a restart at ``now`` is allowed; counted when it is."""
        while self._at and now - self._at[0] > self.window:
            self._at.popleft()
        if len(self._at) >= self.limit:
            return False
        self._at.append(now)
        return True


def say(line: str) -> None:
    print(f"nuspace run: {line}", file=sys.stderr, flush=True)  # noqa: T201


def status(code: int) -> int:
    """A child's return code as a shell tells it: a signal ``n`` is ``128 + n``."""
    return 128 - code if code < 0 else code


def spawn(what: str, root: str, options: bytes) -> subprocess.Popen:
    """One driver's child, its options written on its stdin, the pipe left open."""
    child = subprocess.Popen(  # noqa: S603 -- our own interpreter and module
        [sys.executable, "-m", "nuspace.space.local.child", what, root],
        stdin=subprocess.PIPE,
        start_new_session=True,
    )
    assert child.stdin is not None  # noqa: S101 -- PIPE asked for above
    child.stdin.write(options)
    child.stdin.flush()
    return child


def stop(child: subprocess.Popen | None, grace: float = GRACE) -> None:
    """``child`` stopped as at a Ctrl+C, killed past ``grace``, reaped. Gone already is fine."""
    if child is None:
        return
    if child.poll() is None:
        with contextlib.suppress(ProcessLookupError):
            child.send_signal(signal.SIGINT)
        try:
            child.wait(grace)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()
    if child.stdin is not None:
        with contextlib.suppress(OSError):
            child.stdin.close()


async def supervise(root: str, kernel: bytes, web: bytes, rest: bytes) -> int:
    """Run both children on ``root`` until the kernel exits or this is cancelled; the kernel's status.

    Args:
        root: The space's root, absolute.
        kernel: The kernel's options, pickled.
        web: Web's options, pickled, for its first start.
        rest: Web's options, pickled, for a restart (no tab opened).
    """
    kernel_child = spawn("kernel", root, kernel)
    web_child = None
    try:
        valkey = binding.valkey_dir(data_dir(root))
        deadline = time.monotonic() + KERNEL_UP
        while not answers(valkey):
            code = kernel_child.poll()
            if code is not None:
                say(f"the kernel exited ({status(code)}) before it came up")
                return status(code)
            if time.monotonic() >= deadline:
                say(f"the kernel did not come up within {KERNEL_UP:.0f} s, stopping")
                return 1
            await asyncio.sleep(POLL)
        web_child = spawn("web", root, web)
        restarts = Restarts()
        while True:
            await asyncio.sleep(POLL)
            code = kernel_child.poll()
            if code is not None:
                say(f"the kernel exited ({status(code)}), stopping web")
                return status(code)
            code = web_child.poll()
            if code is None:
                continue
            if code == REFUSED:
                say("web was refused, stopping the kernel")
                return REFUSED
            if not restarts.allow(time.monotonic()):
                log = data_dir(root) / WEB_LOG
                say(f"web exited {RESTARTS + 1} times within {WINDOW:.0f} s, stopping. See {log}")
                return 1
            say(f"web exited ({status(code)}), starting it again")
            stop(web_child)
            web_child = spawn("web", root, rest)
    finally:
        stop(web_child)
        stop(kernel_child)


class ChildrenRef(Ref):
    """The Ref naming run's child processes, what :class:`Supervised` writes. Nothing is bound.

    Declared so the engine keeps the run ordered and never folds it away
    as a pure read.

    Yields:
        None.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        return lambda rt: None

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> None:
            return None

        return athunk


class Supervised(Command):
    """:func:`supervise` as a term: yields the kernel's exit status. Async only.

    Args:
        root: The space's root, absolute.
        kernel: The kernel's options, pickled.
        web: Web's options, pickled, first start.
        rest: Web's options, pickled, restarts.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, root: str, kernel: bytes, web: bytes, rest: bytes) -> None:
        super().__init__(ChildrenRef())
        self._payload = dict(self._payload)
        self._payload.update(root=root, kernel=kernel, web=web, rest=rest)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            msg = "local.run runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        p = self._payload

        async def athunk(rt: Runtime) -> int:
            return await supervise(p["root"], p["kernel"], p["web"], p["rest"])

        return athunk


def pickled(what: str, options: Mapping[str, object]) -> bytes:
    try:
        return pickle.dumps(dict(options))
    except (pickle.PicklingError, TypeError, AttributeError) as e:
        msg = (
            f"local.run hands the {what} its options in another process, and they must pickle: {e}"
        )
        raise TypeError(msg) from None


def run(
    path: str | os.PathLike[str] | None = None,
    *,
    plane: PlaneSpec | str | None = None,
    **options: object,
) -> nu.With:
    """The space at ``path`` with its kernel and its web in two processes, watched over.

    See the module for what happens when either stops. Yields the kernel's
    exit status, 0 at a Ctrl+C.

    Args:
        path: The space's root, made if missing. None is a throwaway one,
            removed at the end.
        plane: A plane spec, or its registered name, web opens on (see
            ``local.web``). Resolved or made by web, so a restarted web
            finds the same plane.
        **options: ``local.kernel``'s and ``local.web``'s options, each
            handed to the entry point that takes it (``extensions`` and
            ``blobs`` to both), pickled: they must pickle.

    Raises:
        TypeError: An option neither entry point takes, or one that does not pickle.
        Missing: No plane spec of the name ``plane``.
    """
    unknown = set(options) - KERNEL - WEB
    if unknown:
        msg = f"local.run got options no entry point takes: {', '.join(sorted(unknown))}"
        raise TypeError(msg)
    if plane is not None:
        found(plane)
    root, throwaway = resolve_root(path)
    kernel = {k: v for k, v in options.items() if k in KERNEL}
    web = {k: v for k, v in options.items() if k in WEB}
    if plane is not None:
        web["plane"] = plane
    term = Supervised(
        root,
        pickled("kernel", kernel),
        pickled("web", web),
        pickled("web", {**web, "open_browser": False}),
    )
    held = [nu.Provide(Throwaway, {"path": root})] if throwaway else []
    return nu.With(*held, body=term)
