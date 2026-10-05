"""The ``ticker`` snippet: a cell that draws.

One stat tile, and a count kept in its own state, one a second while the
plane is up.
"""

from __future__ import annotations

from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


SOURCE = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out():
    tile = nustd.ui.StatRef("seconds")
    # One short commit per tick, never one held across the loop.
    step = ops.atomic_state(Tick.n.set(Tick.n.fallback(0) + 1) >> tile.set_value(nu.str(Tick.n)))
    return tile.set_label("Seconds this plane was open") >> nu.ForeverDo(nu.DelayedDo(1.0, step))
"""

SNIPPET = Snippet("ticker", "Ticker", SOURCE)
