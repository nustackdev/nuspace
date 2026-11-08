"""Reap: at open, whatever the live indexes still list was left by a host that is gone.

Runs once at open, after the lock, the format check and a fresh conn.db,
before spare workers and drivers: the kernel trusts the live indexes, so
they must say the truth before it folds over them. A plane run, cell run or
worker still listed live belongs to a host that died without ending it.
Each is ended ``killed`` with a warning on stderr, then ``indexes.live`` is
erased and made again, empty.

The processes are not touched: a worker dies with its host (mp_pool's
parent watch kills a worker whose host is gone). Kill by handle, the
backend's ``areap``, comes in only if leftovers show up.

Walks the live indexes only, never history: O(what was live). Never blocks
an open: should the warnings fail, that is reported and the ends go on;
should the ends fail (indexes a crash left half written), the failure is
reported and ``live`` is cleared anyway, the records left as they are.
"""

from __future__ import annotations

import nu
from nu.core.io import STDERR
from nuspace.host.stores import init_live
from nuspace.ops.brackets import atomic
from nuspace.shapes import EXIT_KILLED, Space

from .interactions import ErrorText
from .records import end_cell_run, end_plane_run, end_worker, keys


__all__ = ["LEFT_OVER", "reap"]


#: The error a reaped run or worker is ended with.
LEFT_OVER = "Left live by a host that is gone, reaped at open"

_live = Space.exec.indexes.live


def _warn(*parts: object) -> nu.Nu:
    """One line on stderr: ``nuspace reap: ...``."""
    return nu.Print(STDERR, "nuspace reap: ", *parts, sep="")


def _warnings() -> nu.Nu:
    """A line per leftover plane run and per leftover worker, read before anything is ended."""
    runs = Space.exec.plane_runs
    workers = Space.exec.workers
    return nu.ForEachDo(
        keys(_live.plane_runs),
        lambda r: _warn(
            "plane run ",
            r,
            " of plane ",
            runs[nu.Str(r)].plane.fallback("?"),
            " was left live, ending it killed",
        ),
    ) >> nu.ForEachDo(
        keys(_live.workers),
        lambda w: _warn(
            "worker ",
            w,
            " on ",
            workers[nu.Str(w)].backend.fallback("?"),
            " was left live, ending it killed",
        ),
    )


def _clear() -> nu.Nu:
    """``indexes.live`` erased and made again, empty. Bare."""
    return _live.erase() >> init_live()


def _ends() -> nu.Nu:
    """Every leftover cell run, worker and plane run ended killed, then live cleared. Bare.

    Cell runs first, read off every plane run that still has a live cell
    run set (an ended plane run keeps one until its last cell run ends).
    """
    by_run = _live.plane_run_to_cell_runs
    cell_runs = nu.ForEachDo(
        keys(by_run),
        lambda r: nu.ForEachDo(
            keys(by_run[nu.Str(r)].ids),
            lambda cr: end_cell_run(nu.Str(cr), EXIT_KILLED, LEFT_OVER),
        ),
    )
    workers = nu.ForEachDo(
        keys(_live.workers), lambda w: end_worker(nu.Str(w), EXIT_KILLED, LEFT_OVER)
    )
    plane_runs = nu.ForEachDo(
        keys(_live.plane_runs), lambda r: end_plane_run(nu.Str(r), EXIT_KILLED, LEFT_OVER)
    )
    return cell_runs >> workers >> plane_runs >> _clear()


def reap() -> nu.Nu:
    """End what the last open left live, killed, with a warning; then clear ``indexes.live``.

    Two steps: the warnings, read in a snapshot, then one commit. Each
    step catches its own raise, so neither blocks the open. Cost: O(what
    was live).
    """

    def unlisted(err: nu.Nu) -> nu.Nu:
        return _warn("could not list the leftovers: ", ErrorText(err))

    def cleared(err: nu.Nu) -> nu.Nu:
        why = ErrorText(err)
        return _warn("could not end the leftovers, clearing live only: ", why) >> atomic(_clear())

    warned = nu.TryCatch(atomic(_warnings()), catch=unlisted)
    return warned >> nu.TryCatch(atomic(_ends()), catch=cleared)
