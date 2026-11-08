"""Small things services and system cells share: the store snapshot and the error policies.

**Snapshot.** :func:`snap` reads a term in a snapshot of both stores, each
opened only if read. One implementation (:func:`nuspace.ops.utils.snapshot`);
this is its public path.

**Error policies.** An unhandled raise in a fold arm ends the whole fold, so
every arm says what happens on one. Each policy reports through
:func:`report`, one line on the cell run's stdout:

- :func:`restarting`, services (supervisor, nav, reload, reactions) and the
  kernel's init start: the arm runs again after a short delay, every
  failure reported.
- :func:`isolated`, web arms: the arm ends, reported, the rest keeps going.
- kernel arms end their run or cell run as failed, in the kernel itself.
"""

from __future__ import annotations

import nu
from nu.core.io import STDOUT
from nuspace.ops.utils import snapshot as snap


__all__ = ["isolated", "report", "restarting", "snap"]


def report(name: str, id: nu.StrArg | None, error: nu.Nu) -> nu.Nu:
    """One line on stdout: ``nuspace <name> <id>: <error>``.

    Args:
        name: The fold or plane that failed, eg ``"supervisor"`` or ``"web viewer"``.
        id: The arm's id (a plane, a run, an op name), any ``StrArg``, or
            None for an arm with no id.
        error: The error, as a policy hands it.
    """
    head = nu.Str(f"nuspace {name}")
    if id is not None:
        head = head + " " + nu.str(id)
    return nu.Print(STDOUT, head, ": ", nu.str(error), sep="")


def restarting(
    arm: nu.Nu, name: str, id: nu.StrArg | None = None, *, delay: nu.FloatArg = 0.1
) -> nu.Nu:
    """``arm``, run again ``delay`` seconds after every raise, each failure reported.

    The services policy. An arm error is reported and the arm runs again
    after ``delay``, the same wait every time. Backoff is for external
    services that need room to recover, not for these: a service arm reads
    the store, and a raise there is a bug to see, not load to shed. Never
    gives up: it ends when the arm returns or the caller cancels.
    """
    return nu.Retry(
        arm,
        max_attempts=None,
        delay=delay,
        on_attempt_fail=lambda err, attempt: report(name, id, err),
    )


def isolated(arm: nu.Nu, name: str, id: nu.StrArg | None = None) -> nu.Nu:
    """``arm``, its raise reported and swallowed: the arm ends, its siblings keep going.

    The web policy.
    """
    return nu.TryCatch(arm, catch=lambda err: report(name, id, err))
