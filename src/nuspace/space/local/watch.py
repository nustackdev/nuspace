"""local.run: infra held here, the kernel and web each in a worker of one ``nustd.mp`` pool, as one tree.

The run process holds infra itself (``local.infra``, its body the pool):
the notification server lives as long as run does. The kernel and web run
in two workers of one pool, so web can stop and start again (a crash, an
extension installed) while the kernel and every plane run it holds go on,
and a kernel that dies takes neither the server nor web with it. They
share nothing in memory: the stores, the notifier and local's files are
all they meet through.

Run is a plain tree: a ``nu.Race`` of two arms inside the pool inside
infra, each arm teleporting its driver's term to a fresh worker. A driver's
term is built with the tree, on the root as the caller gave it: a path, or
the ``nu.Attr`` a ``nustd.fs.tmp`` lambda hands over a throwaway root. The
teleport carries the caller's attrs (``carry=True``), so a throwaway root,
known only once its dir is made, reaches both workers as the path it is.
Building a term opens nothing: whatever a driver holds (the uploads area, a
server) is opened in its worker, when the term runs there.

- **Start.** Infra's checks, lock and server here, then both arms at once:
  the kernel's worker, and web's once the kernel holds its lock (a kernel
  holding its lock has infra answering), or refused after
  :data:`KERNEL_UP` seconds.
- **Ctrl+C**, or the term cancelled: both arms are cancelled, which
  cancels the drivers in their workers, and the pool closes, stopping both
  workers at once within :data:`GRACE` (its stop ladder: a polite stop,
  then SIGINT, SIGTERM, SIGKILL). Then infra closes here.
- **The tab**: opened here, once, beside web's first start (:func:`tab`),
  on the url web would have opened, a plane resolved or made here first.
  Web's term is built once and opens none: a restarted web is the same
  term, so it opens none either and keeps one session address (the tab
  reconnects on its own, the kernel's envs read the same address).
- **Web ends**, however it ends: started again in a fresh worker through
  ``nu.Retry``, which takes every end for a failure (a clean one raises):
  :data:`RESTARTS` times at most, waiting :data:`DELAY` seconds doubled
  each time up to :data:`MAX_DELAY`. Past that, run stops, saying why.
  Refused (a web runs elsewhere) is what ``Retry`` never retries: run
  stops at once.
- **The kernel ends**: the race is over, closing the pool stops web, and
  run ends with the kernel's status (:func:`ended`). Infra answers
  until then: the server never went with the kernel.
- **path None**: one throwaway root, made and initialized here before
  infra's init check (:func:`~.opening.fresh`); both workers use it, and it
  is removed once all is gone. Any other path must be initialized already
  (``local.init``): infra's init check refuses it.

What a driver starts in its own worker ends with it. The kernel's cell
workers lead their own process groups and each watches its parent, the
kernel's worker: gone, however it went, they end their groups themselves;
stopped politely, the kernel's own pool closes them first. Web holds no
workers: what nav runs, the kernel runs. All of it is ``nustd.mp``'s
doing, nothing here.

The workers' stdout and stderr are this process's: web's server says where
it listens, the kernel what it reaps. This process only says how each
ended, on stderr, prefixed ``nuspace run:``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.mp
from nu.core.io import STDERR
from nu.lang import wire
from nuspace.errors import Refused
from nuspace.kernel.interactions import ErrorText
from nustd.webbrowser import tab_opened

from ..blocks.meta import said
from ..blocks.required import required
from . import binding, drivers
from .disk import held
from .layout import DATA, KERNEL_LOCK, WEB_LOG
from .opening import ROOTS, fresh
from .plane import found


if TYPE_CHECKING:
    import os
    from collections.abc import Mapping

    from nu.context.fabric import Provide
    from nuspace.specs import PlaneSpec


__all__ = ["GRACE", "REFUSED", "RESTARTS", "ended", "run"]


#: The status run ends with when a driver was refused: run does not try again.
REFUSED = 2

#: How many times run starts web again before it stops, and the waits between:
#: ``DELAY`` seconds before the first restart, doubled each time, at most ``MAX_DELAY``.
RESTARTS = 5
DELAY = 1.0
MAX_DELAY = 30.0

#: Seconds the pool gives its workers to stop when it closes, polite first,
#: killed past it. The kernel's close ends what is live and stops its own
#: workers in this time.
GRACE = 30.0

#: Seconds web waits for the kernel to hold its lock before it is refused.
KERNEL_UP = 60.0

#: The pool's name, as each worker's title shows it, and the tag it binds under.
POOL_NAME = "nuspace-run"
POOL_TAG = "nuspace.local.run"

#: The pool run's workers are launched from.
POOL = nustd.mp.PoolRef(POOL_TAG)

#: The options each entry point takes, so ``run`` hands each its own.
KERNEL = frozenset({"extensions", "envs", "space_envs", "backends", "spares", "name", "blobs"})
WEB = frozenset({"extensions", "host", "port", "static", "open_browser", "blobs", "blob_backend"})


def say(*parts: object) -> nu.Nu:
    """One line on stderr: ``nuspace run: ...``."""
    return nu.Print(STDERR, "nuspace run: ", *parts, sep="")


def put(into: nu.Ref | None, code: object) -> nu.Nu:
    """``code`` written to ``into``; nothing when there is no ``into``."""
    return nu.Noop() if into is None else into.set(code)


def in_worker(term: nu.Nu) -> nu.Nu:
    """``term`` run in a fresh worker of the pool, the caller's attrs carried; its value or its error here.

    The worker is stopped after, however the term ended: one gone already
    stops at once.
    """
    return nu.let(
        POOL.launch(),
        lambda w: nu.TryCatch(POOL.teleport(term, w, carry=True), finally_=POOL.stop(w)),
    )


def _gone(exc: nu.Nu) -> nu.Nu:
    """A ``WorkerGone``'s exit code as a shell tells it: a signal ``n`` is ``128 + n``, unknown 1."""
    code = nu.GetAttr(exc, "exitcode")
    return nu.If(nu.Is(code, None), 1, nu.If(nu.Lt(code, 0), nu.Sub(128, code), code))


def ended(err: nu.Nu) -> nu.Tuple:
    """How a driver ended, from its error: ``(status, words)``, eg ``(137, "exited (137, crashed)")``.

    Refused is 2, ``was refused (...)``; interrupted 0; a gone worker its
    exit code; anything else 1, ``failed (Type: message)``.

    Args:
        err: What a catch or a ``Retry`` hook binds, a ``CaughtError``.
    """
    exc = nu.GetAttr(err, "exception")
    code, cause = _gone(exc), nu.GetAttr(exc, "cause")
    gone = said(
        "exited ({code}, {cause})", code=code, cause=nu.If(nu.Is(cause, None), "gone", cause)
    )
    return nu.Tuple(
        nu.If(
            nu.IsInstance(exc, Refused),
            nu.Tuple.of(REFUSED, said("was refused ({why})", why=nu.Str(err))),
            nu.If(
                nu.IsInstance(exc, nustd.mp.Interrupted),
                nu.Tuple.of(0, "was interrupted"),
                nu.If(
                    nu.IsInstance(exc, nustd.mp.WorkerGone),
                    nu.Tuple.of(code, gone),
                    nu.Tuple.of(1, said("failed ({error})", error=ErrorText(err))),
                ),
            ),
        )
    )


def stopping(who: str, err: nu.Nu, then: str, into: nu.Ref | None) -> nu.Nu:
    """``who`` ended as ``err`` tells, said with ``then`` after it, its status written to ``into``."""
    return nu.let(ended(err), lambda e: say(who, nu.Tuple(e)[1], then) >> put(into, nu.Tuple(e)[0]))


def kernel_arm(kernel: nu.Nu, into: nu.Ref | None) -> nu.Nu:
    """The kernel in its worker; its end said and its status written to ``into``."""
    return nu.TryCatch(
        in_worker(kernel) >> say("the kernel ended, stopping web") >> put(into, 0),
        catch=lambda err: stopping("the kernel ", err, ", stopping web", into),
    )


def web_arm(web: nu.Nu, beside: nu.Nu | None, into: nu.Ref | None) -> nu.Nu:
    """Web in a worker once the kernel is up, started again when it ends, ``beside`` with it; a refusal or a give up written to ``into``.

    Every end of web is a failure to ``Retry``: one without an error
    raises once its worker is done. A refusal is excluded from what is
    retried and ends the arm. The hooks bind the error only while they
    run, so nothing caught is in the attrs a restart carries to its worker.
    """
    up = required(
        held(DATA / KERNEL_LOCK),
        f"the kernel did not come up within {KERNEL_UP:.0f} s",
        wait=KERNEL_UP,
    )
    restarted = nu.Retry(
        in_worker(web) >> nu.Raise("ended on its own"),
        max_attempts=RESTARTS + 1,
        delay=DELAY,
        backoff=2.0,
        max_delay=MAX_DELAY,
        except_errors=Refused,
        on_attempt_fail=lambda err, attempt: say("web ", ended(err)[1], ", starting it again"),
        on_fail=lambda err, attempt: (
            say(
                "web ",
                ended(err)[1],
                f", {RESTARTS + 1} times, stopping. See ",
                DATA.where(WEB_LOG),
            )
            >> put(into, 1)
        ),
    )
    return nu.TryCatch(
        up >> (restarted if beside is None else nu.Race(restarted, beside)),
        catch=lambda err: stopping("web ", err, ", stopping the kernel", into),
        errors=Refused,
    )


def tab(
    plane: PlaneSpec | str | None, *, browse: bool, host: str, port: int, blobs: Provide | None
) -> nu.Nu | None:
    """What runs beside web's restarts in this process, once: the tab web's first start would have opened, then held.

    The url is web's own: its server's on home, ``/p/<plane>`` on a plane.
    A plane is resolved or made here, once, with the stores bound (as
    ``local.open`` binds them), so every web start serves the same one.
    None when there is neither a plane nor a tab.
    """
    if plane is not None:
        blobs = binding.blobs() if blobs is None else blobs
        on = drivers.opened_on(found(plane), browse=browse, host=host, port=port)
        return nu.With(binding.stores(ROOTS), blobs, body=on)
    if not browse:
        return None
    # As the server says where it runs: localhost for a loopback or any interface.
    shown = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host  # noqa: S104
    return tab_opened(f"http://{shown}:{port}", host, port) >> nu.Park()


def pickled(what: str, options: Mapping[str, object]) -> Mapping[str, object]:
    """``options``, checked to pickle: the entry point's term carries them to its worker.

    Checked here, when run is built, so a bad option is told at once rather
    than when infra is up and the teleport fails.

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


def run(
    path: str | os.PathLike[str] | nu.Nu | None = None,
    *,
    into: nu.Ref | None = None,
    plane: PlaneSpec | str | None = None,
    **options: object,
) -> nu.Nu:
    """The space at ``path``: infra in this process, its kernel and its web in two workers of one pool.

    See the module for what happens when either stops. Yields nothing: the
    status lands in ``into``, nothing at a Ctrl+C.

    Args:
        path: The space's root, initialized (``local.init``), or a term
            yielding it that reads the same in the workers, eg the
            ``nu.Attr`` a ``nustd.fs.tmp`` lambda hands. None is a
            throwaway one, made and initialized here, removed at the end.
        into: Where run's status is written, eg an ``nu.IntRef`` slot the
            caller binds and reads after: the kernel's, or 2 when web was
            refused, 1 when web ended too often. None records it nowhere.
        plane: A plane spec, or its registered name, the tab opens on (see
            ``local.web``). Resolved or made here once, beside web's first
            start (:func:`tab`).
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
    kernel = pickled("kernel", {k: v for k, v in options.items() if k in KERNEL})
    web = pickled("web", {k: v for k, v in options.items() if k in WEB})
    beside = tab(
        plane,
        browse=web.get("open_browser", True),
        host=web.get("host", "127.0.0.1"),
        port=web.get("port", 8080),
        blobs=web.get("blobs"),
    )

    def on(root: str | nu.Nu) -> nu.Nu:
        served = drivers.web(root, **{**web, "open_browser": False})
        race = nu.Race(
            kernel_arm(drivers.kernel(root, **kernel), into), web_arm(served, beside, into)
        )
        pooled = nustd.mp.pool(name=POOL_NAME, grace=GRACE, tags=(POOL_TAG,), body=race)
        return drivers.infra(root, body=pooled)

    return fresh(path, on)
