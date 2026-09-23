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


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out():
    tile = nustd.ui.StatRef("seconds")
    now = nu.If(Tick.n.exists(), nu.Int(nu.ToInt(Tick.n)), nu.Int(0))
    step = Tick.n.set(now + nu.Int(1)) >> tile.set_value(nu.ToStr(Tick.n))
    return tile.set_label("seconds this plane was open") >> nu.ForeverDo(nu.DelayedDo(1.0, step))
"""

SNIPPET = Snippet("ticker", "Ticker", SOURCE)
