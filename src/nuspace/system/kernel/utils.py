"""Small things the kernel's modules share. Helpers, not concepts."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.shapes import Space, States


__all__ = ["PARK_SECONDS", "park", "snap"]


#: How long a parked branch sleeps between doing nothing.
PARK_SECONDS = 3600.0


def park() -> nu.Nu:
    """Sit until cancelled. What an arm does instead of ending, so a fold does not respawn it."""
    return nu.ForeverDo(nu.Delay(PARK_SECONDS))


def snap(term: nu.Nu) -> nu.Nu:
    """``term`` read in a snapshot of both stores, each opened only if read."""
    return nustd.kv.Snapshot(nustd.kv.Snapshot(term, scope=States), scope=Space)
