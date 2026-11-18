"""A requirement: what an entry point needs running before it starts, or a refusal saying what to start.

The layers of a space assume the ones under them and never check: a
driver fails as it fails when what it runs on goes. So the check lives in
the entry point, once, before anything else: the kernel's needs infra
answering, web's needs a kernel running. :func:`required` is that check as
flow, a step to put before the body (``Guarded(body, required(...))``).

A requirement may be coming up beside the entry point, eg two shells
started at once, or a supervisor starting its children in order. So it
looks again for a moment before it refuses: a short ``grace`` always,
and up to ``wait`` seconds while ``waiting`` says it is on its way (a lock
held, its server not up yet). Async only, as every entry point runs.
"""

from __future__ import annotations

import nu
from nuspace.errors import Refused


__all__ = ["EVERY", "required"]


#: How often a requirement looks again while it waits.
EVERY = 0.05


def looking(seconds: float, cond: nu.Nu) -> nu.Nu:
    """Look again every :data:`EVERY` seconds while ``cond`` holds, for ``seconds`` at most."""
    return nu.Timeout(seconds, nu.WhileDo(cond, nu.Delay(EVERY)), on_timeout=nu.Noop())


def required(
    check: nu.Nu,
    refusal: str,
    *,
    wait: float = 10.0,
    waiting: nu.Nu | None = None,
    grace: float = 0.0,
) -> nu.Nu:
    """``check`` holding now, or within ``wait`` seconds, else a refusal. Yields nothing.

    It looks again while less than ``grace`` seconds have passed, or less
    than ``wait`` and ``waiting`` holds.

    Args:
        check: A query: whether the requirement holds now.
        refusal: What a refusal says, eg ``"infra of this space is not
            running: start it first"``.
        wait: Seconds to wait at most.
        waiting: A query: whether what is required is on its way, asked at
            each look. None waits the whole ``wait``.
        grace: Seconds to look again whatever ``waiting`` says: for what is
            required starting beside this, not showing it yet.

    Raises:
        Refused: (at run) ``check`` did not hold in time.
    """
    missing = nu.Not(check)
    if waiting is None:
        looks = looking(wait, missing)
    else:
        first = min(grace, wait)
        looks = looking(first, missing) >> looking(wait - first, nu.And(missing, waiting))
    return looks >> nu.IfDo(missing, nu.Raise(refusal, exc_cls=Refused))
