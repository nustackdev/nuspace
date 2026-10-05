"""A ticker: one stat tile, and a count kept in its own state, one a second while the plane is up."""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["Tick", "out"]


class Tick(nuspace.CellState):
    """The ticker's state: the seconds counted so far."""

    n = nustd.kv.IntRef.slot()


def out() -> nu.Nu:
    """Count a second at a time, for as long as the cell runs, and show the count."""
    tile = nustd.ui.StatRef("seconds")
    # One short commit per tick, never one held across the loop.
    step = ops.atomic_state(Tick.n.set(Tick.n.fallback(0) + 1) >> tile.set_value(nu.str(Tick.n)))
    return tile.set_label("Seconds this plane was open") >> nu.ForeverDo(nu.DelayedDo(1.0, step))
