"""local.run: infra held here, the kernel and web each in a worker of one ``nustd.mp`` pool, watched over.

The run process holds infra itself (``local.infra``, its body the pool):
the notification server lives as long as run does. The kernel and web run
in two workers of one pool, so web can stop and start again (a crash, an
extension installed) while the kernel and every plane run it holds go on,
and a kernel that dies takes neither the server nor web with it. They
share nothing in memory: the stores, the notifier and local's files are
all they meet through.

Each driver's term is built here, when run starts its workers, and
teleported to its worker as it is: the entry point (``drivers.kernel``,
``drivers.web``) called on the root's ``where()``, a plain path by then,
so a throwaway root's temp dir reaches both as the path it is. Building a
term opens nothing: whatever a driver holds (the uploads area, a server)
is opened in its worker, when the term runs there.

- **Start.** Infra's checks, lock and server here, then the kernel's
  worker, then web's once the kernel's lock is held (a kernel holding its
  lock has infra answering). Each runs through a teleport of its own task,
  so how it ends arrives here: a clean end, a refusal, or ``WorkerGone``
  with its cause and exit code.
- **Ctrl+C**, or the term cancelled: both teleports are cancelled, which
  cancels the drivers in their workers, and the pool closes, stopping both
  workers at once within :data:`GRACE` (its stop ladder: a polite stop,
  then SIGINT, SIGTERM, SIGKILL). No order: a kernel closing before web is
  fine, web's tabs only wait. Then infra closes here.
- **Web ends**: started again in a fresh worker, without opening a tab
  (the tab reconnects on its own). More than :data:`RESTARTS` times within
  :data:`WINDOW` seconds, or refused (a web runs elsewhere), and run stops,
  saying why.
- **The kernel ends**: run ends with the kernel's status, and closing the
  pool stops web. Infra answers until then: the server never went with the
  kernel.
- **path None**: one throwaway root, a ``nustd.fs.tmp`` dir, made and
  initialized here before infra's init check; both workers use it, and it
  is removed once all is gone. Any other path must be initialized already
  (``local.init``): infra's init check refuses it.

What a driver starts in its own worker ends with it. The kernel's cell
workers lead their own process groups and each watches its parent, the
kernel's worker: gone, however it went, they end their groups themselves;
stopped politely, the kernel's own pool closes them first. Web holds no
workers: what nav runs, the kernel runs. All of it is ``nustd.mp``'s
doing, nothing here.

The workers' stdout and stderr are this process's: web's server says where
it listens, the kernel what it reaps. This process only says what it does
to them, on stderr, prefixed ``nuspace run:``.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import sys
import time
from collections import deque
from typing import TYPE_CHECKING

import nu
import nustd.mp
from nu.engine.structure import Declared
from nu.lang import wire
from nuspace.errors import Refused

from . import drivers
from .disk import held
from .layout import DATA, KERNEL_LOCK, ROOT, WEB_LOG
from .opening import fresh
from .plane import found


if TYPE_CHECKING:
    import os
    from collections.abc import Awaitable, Callable, Mapping

    from nu.lang.runtime import Runtime
    from nuspace.specs import PlaneSpec


__all__ = ["GRACE", "REFUSED", "RESTARTS", "WINDOW", "Restarts", "Watched", "run"]


#: The status run ends with when a driver was refused: run does not try again.
REFUSED = 2

#: How many web restarts run allows within :data:`WINDOW` seconds.
RESTARTS = 5
WINDOW = 60.0

#: Seconds the pool gives its workers to stop when it closes, polite first,
#: killed past it. The kernel's close ends what is live and stops its own
#: workers in this time.
GRACE = 30.0

#: How often run looks for the kernel's lock while the kernel comes up.
POLL = 0.1

#: Seconds run waits for the kernel to hold its lock before it gives up.
KERNEL_UP = 60.0

#: The pool's name, as each worker's title shows it, and the tag it binds under.
POOL_NAME = "nuspace-run"
POOL_TAG = "nuspace.local.run"

#: The pool run's workers are launched from.
POOL = nustd.mp.PoolRef(POOL_TAG)

#: The options each entry point takes, so ``run`` hands each its own.
KERNEL = frozenset({"extensions", "envs", "space_envs", "backends", "spares", "name", "blobs"})
WEB = frozenset({"extensions", "host", "port", "static", "open_browser", "blobs", "blob_backend"})


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
    """An exit code as a shell tells it: a signal ``n`` is ``128 + n``."""
    return 128 - code if code < 0 else code


def ended(run: asyncio.Task) -> tuple[int, str]:
    """How a driver's teleport ended: the status run takes from it, and how ``say`` tells it."""
    exc = run.exception()
    if exc is None:
        return 0, "ended"
    if isinstance(exc, Refused):
        return REFUSED, f"was refused ({exc})"
    if isinstance(exc, nustd.mp.Interrupted):
        return 0, "was interrupted"
    if isinstance(exc, nustd.mp.WorkerGone):
        code = 1 if exc.exitcode is None else status(exc.exitcode)
        return code, f"exited ({code}, {exc.cause or 'gone'})"
    return 1, f"failed ({type(exc).__name__}: {exc})"


async def teleported(pool: nustd.mp.WorkerPool, term: nu.Nu) -> object:
    """``term`` run in a fresh worker of ``pool``, its value or its error here.

    A worker whose term ended, raised or not, is still up and idle: it is
    stopped before this returns. One cancelled is left to the pool's close.
    """
    wid = await pool.alaunch()
    try:
        value = await pool.ateleport(wid, term)
    except nustd.mp.WorkerGone:
        raise
    except Exception:
        await stopped(pool, wid)
        raise
    await stopped(pool, wid)
    return value


async def stopped(pool: nustd.mp.WorkerPool, wid: int) -> None:
    """Worker ``wid`` stopped, within the pool's grace. Gone already is fine."""
    with contextlib.suppress(nustd.mp.UnknownWorker, nustd.mp.WorkerGone):
        await pool.astop(wid)


async def watch(
    pool: nustd.mp.WorkerPool,
    kernel: nu.Nu,
    web: nu.Nu,
    rest: nu.Nu,
    up: Callable[[], Awaitable[object]],
    log: str,
) -> int:
    """Run the kernel and web in ``pool`` until the kernel ends or this is cancelled; the kernel's status.

    Infra runs already: this is its body.

    Args:
        pool: The pool both workers are launched from.
        kernel: The kernel's term, built here, run in its worker.
        web: Web's term, for its first start.
        rest: Web's term, for a restart (no tab opened).
        up: Whether the kernel holds its lock now.
        log: Web's log file, as a give up names it.
    """
    runs: list[asyncio.Task] = []

    def started(term: nu.Nu) -> asyncio.Task:
        task = asyncio.ensure_future(teleported(pool, term))
        runs.append(task)
        return task

    try:
        kernel_run = started(kernel)
        deadline = time.monotonic() + KERNEL_UP
        while not await up():
            if kernel_run.done():
                code, how = ended(kernel_run)
                say(f"the kernel {how} before it came up")
                return code
            if time.monotonic() >= deadline:
                say(f"the kernel did not come up within {KERNEL_UP:.0f} s, stopping")
                return 1
            await asyncio.sleep(POLL)
        web_run = started(web)
        restarts = Restarts()
        while True:
            await asyncio.wait({kernel_run, web_run}, return_when=asyncio.FIRST_COMPLETED)
            if kernel_run.done():
                code, how = ended(kernel_run)
                say(f"the kernel {how}, stopping web")
                return code
            code, how = ended(web_run)
            if code == REFUSED:
                say(f"web {how}, stopping the kernel")
                return REFUSED
            if not restarts.allow(time.monotonic()):
                say(f"web ended {RESTARTS + 1} times within {WINDOW:.0f} s, stopping. See {log}")
                return 1
            say(f"web {how}, starting it again")
            web_run = started(rest)
    finally:
        # No ordered stop: the pool's close stops both workers at once.
        for run in runs:
            run.cancel()
        await asyncio.gather(*runs, return_exceptions=True)


class Watched(nu.ScalarAction):
    """:func:`watch` as a term: yields the kernel's status. Async only.

    Args:
        pool: The pool, a ``nustd.mp.PoolRef``.
        kernel: A query yielding the kernel's term (:func:`shipped`): data
            shipped to its worker, never run here.
        web: A query yielding web's term for its first start.
        rest: A query yielding web's term for a restart.
        up: A query: whether the kernel holds its lock, asked at each look.
        log: Web's log file, absolute, or a query yielding it, as a give up names it.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(
        self, pool: nu.Nu, kernel: nu.Nu, web: nu.Nu, rest: nu.Nu, up: nu.Nu, log: nu.StrArg
    ) -> None:
        super().__init__(pool, kernel, web, rest, up, log)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            msg = "local.run runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        pool_of, kernel_of, web_of, rest_of, up, log_of = children

        async def athunk(rt: Runtime) -> int:
            pool = await pool_of(rt)
            if not isinstance(pool, nustd.mp.WorkerPool):
                msg = "local.run needs its worker pool bound"
                raise RuntimeError(msg)
            kernel, web, rest = await kernel_of(rt), await web_of(rt), await rest_of(rt)
            log = str(await log_of(rt))
            return await watch(pool, kernel, web, rest, lambda: up(rt), log)

        return athunk


def pickled(what: str, options: Mapping[str, object]) -> Mapping[str, object]:
    """``options``, checked to pickle: the entry point's term carries them to its worker.

    Checked here, when run is built, so a bad option is told at once.

    Raises:
        TypeError: An option does not pickle.
    """
    try:
        wire.dumps(dict(options))
    except Exception as e:  # whatever cloudpickle raises
        msg = (
            f"local.run hands the {what} its options in another process, and they must pickle: {e}"
        )
        raise TypeError(msg) from None
    return options


def built(entry: Callable[..., nu.Nu], options: Mapping[str, object], root: str) -> nu.Nu:
    """``entry(root, **options)``: the driver's term, teleported to its worker as it is.

    Called where run starts its workers, ``root`` the root's ``where()``
    there: the term holds it as a plain path.
    """
    return entry(root, **options)


def shipped(what: str, entry: Callable[..., nu.Nu], options: Mapping[str, object]) -> nu.Nu:
    """A query yielding the term run ships to a worker for ``entry``: :func:`built` on the root's ``where()``."""
    made = functools.partial(built, entry, pickled(what, options))
    return nu.Literal(factory=made, root=ROOT.where())


def run(
    path: str | os.PathLike[str] | nu.Nu | None = None,
    *,
    into: nu.Ref | None = None,
    plane: PlaneSpec | str | None = None,
    **options: object,
) -> nu.Nu:
    """The space at ``path``: infra in this process, its kernel and its web in two workers, watched over.

    See the module for what happens when either stops. Yields nothing: the
    kernel's status lands in ``into``, 0 at a Ctrl+C.

    Args:
        path: The space's root, initialized (``local.init``), or a term
            yielding it. None is a throwaway one, made and initialized
            here, removed at the end.
        into: Where the kernel's status is written, eg an ``nu.IntRef``
            slot the caller binds and reads after. None records it nowhere.
        plane: A plane spec, or its registered name, web opens on (see
            ``local.web``). Resolved or made by web, so a restarted web
            finds the same plane.
        **options: ``local.kernel``'s and ``local.web``'s options, each
            handed to the entry point that takes it (``extensions`` and
            ``blobs`` to both), pickled to its worker: they must pickle.

    Raises:
        TypeError: An option neither entry point takes, or one that does not pickle.
        Missing: No plane spec of the name ``plane``.
        Refused: A space not initialized, or infra of this space running
            already (at run).
    """
    unknown = set(options) - KERNEL - WEB
    if unknown:
        msg = f"local.run got options no entry point takes: {', '.join(sorted(unknown))}"
        raise TypeError(msg)
    if plane is not None:
        found(plane)
    kernel = {k: v for k, v in options.items() if k in KERNEL}
    web = {k: v for k, v in options.items() if k in WEB}
    if plane is not None:
        web["plane"] = plane

    def on(root: nu.Nu) -> nu.Nu:
        watched = Watched(
            POOL,
            shipped("kernel", drivers.kernel, kernel),
            shipped("web", drivers.web, web),
            shipped("web", drivers.web, {**web, "open_browser": False}),
            held(DATA / KERNEL_LOCK),
            DATA.where(WEB_LOG),
        )
        body = nu.let(0, lambda code: code.set(watched)) if into is None else into.set(watched)
        pooled = nustd.mp.pool(name=POOL_NAME, grace=GRACE, tags=(POOL_TAG,), body=body)
        return drivers.infra(root, body=pooled)

    return fresh(path, on)
