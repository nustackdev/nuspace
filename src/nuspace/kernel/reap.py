"""Reap: as a kernel starts, whatever an earlier kernel started and left live was left by a crash.

The first step of the kernel's driver, before the kernel folds
over the live indexes: it trusts them, so they must say the truth first. A
kernel that closes cleanly ends what it started itself (:mod:`.close`), so
a started plane run, its cell runs, or a worker still listed live belongs
to a kernel that crashed. Each is ended ``killed`` with a warning on
stderr.

Only what a kernel started is a leftover (:func:`.records.end_started`). A
plane run asked for and never started (by nav, by an ``open``, by a system
plane) is an ask: it stays live and pending, and this kernel starts it. So
``live`` is not erased: the ends take what they end out of it, and the
asks stay listed.

The processes are not touched: a worker dies with its kernel (``nustd.mp``'s
parent watch kills a worker whose parent is gone). Kill by handle, the
backend's ``areap``, comes in only if leftovers show up.

Walks the live indexes only, never history: O(what was live). Never blocks
a start: should the warnings fail, that is reported and the ends go on;
should the ends fail (indexes a crash left half written), the failure is
reported and ``live`` is erased and made again, empty, the records left as
they are. That fallback drops the pending asks from ``live`` too: their
rows stay, never started and never ended.
"""

from __future__ import annotations

import nu
from nu.core.io import STDERR
from nuspace.ops.brackets import atomic
from nuspace.shapes import EXIT_KILLED, Space
from nuspace.utils import keys_of

from .interactions import ErrorText
from .live import init_live
from .records import end_started, started


__all__ = ["LEFT_OVER", "reap"]


#: The error a reaped run or worker is ended with.
LEFT_OVER = "Left live by a kernel that is gone, reaped at its next start"

_live = Space.exec.indexes.live


def _warn(*parts: object) -> nu.Nu:
    """One line on stderr: ``nuspace reap: ...``."""
    return nu.Print(STDERR, "nuspace reap: ", *parts, sep="")


def _warnings() -> nu.Nu:
    """A line per started leftover plane run and per leftover worker, read before anything ends."""
    runs = Space.exec.plane_runs
    workers = Space.exec.workers
    return nu.ForEachDo(
        keys_of(_live.plane_runs),
        lambda r: nu.IfDo(
            started(nu.Str(r)),
            _warn(
                "plane run ",
                r,
                " of plane ",
                runs[nu.Str(r)].plane.fallback("?"),
                " was left live, ending it killed",
            ),
        ),
    ) >> nu.ForEachDo(
        keys_of(_live.workers),
        lambda w: _warn(
            "worker ",
            w,
            " on ",
            workers[nu.Str(w)].backend.fallback("?"),
            " was left live, ending it killed",
        ),
    )


def _clear() -> nu.Nu:
    """``indexes.live`` erased and made again, empty. Bare. The fallback only."""
    return _live.erase() >> init_live()


def reap() -> nu.Nu:
    """End what an earlier kernel started and left live, killed, with a warning. Asks stay pending.

    Two steps: the warnings, read in a snapshot, then one commit. Each
    step catches its own raise, so neither blocks the start. Cost: O(what
    was live).
    """

    def unlisted(err: nu.Nu) -> nu.Nu:
        return _warn("could not list the leftovers: ", ErrorText(err))

    def cleared(err: nu.Nu) -> nu.Nu:
        why = ErrorText(err)
        return _warn("could not end the leftovers, clearing live only: ", why) >> atomic(_clear())

    warned = nu.TryCatch(atomic(_warnings()), catch=unlisted)
    return warned >> nu.TryCatch(atomic(end_started(EXIT_KILLED, LEFT_OVER)), catch=cleared)
