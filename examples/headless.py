"""A space with no browser: one plane, one cell counting, read back from the store.

The host body adds a plane with one cell, ups it on a worker, waits for the
count, prints it and returns, which closes the space. The store is a throwaway
directory, gone at close.

Run it::

    python examples/headless.py
"""

from __future__ import annotations

import logging

import nu
import nuspace
import nustd.kv
from nuspace import ops


# Closing the space drops sockets under workers still holding them, and the
# transport logs each one. Expected. At module scope so spawned workers, which
# import this file, are quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


PLANE, CELL = "counter", "count"
TARGET = 5

#: The cell's program. ``Tick`` lands under the cell's own state at load.
COUNT = f"""\
import nu
import nustd.kv
import nuspace


class Tick(nuspace.CellState):
    n = nustd.kv.IntRef.slot()


def out():
    now = nu.If(Tick.n.exists(), nu.Int(nu.ToInt(Tick.n)), nu.Int(0))
    step = Tick.n.set(now + nu.Int(1))
    return nu.ForRangeDo(0, {TARGET}, nu.DelayedDo(0.1, step))
"""


def count() -> nu.Nu:
    """The cell's count, read from the store."""
    return nustd.kv.Snapshot(
        nuspace.Space.planes[PLANE].cells[CELL].state.get_item("n", 0), scope=nuspace.Space
    )


def body() -> nu.Nu:
    """Make the plane, run it, wait for the count, say it."""
    run = nu.Let(
        "example.worker",
        ops.worker(),
        ops.up_plane(PLANE, worker=nu.StrAttrRef("example.worker"), by="example"),
    )
    # Bounded, so a cell that fails does not leave this waiting forever.
    wait = nu.Timeout(10, nu.WhileDo(nu.Lt(nu.ToInt(count()), TARGET), nu.Delay(0.1)))
    return (
        ops.add_plane(PLANE, name="Counter")
        >> ops.add_cell(PLANE, COUNT, cell_id=CELL, name=CELL)
        >> run
        >> wait
        >> nu.print(nu.ToStr(count()))
    )


def main() -> None:
    nu.run_in_loop(nuspace.open_space(web=False, body=body()))


if __name__ == "__main__":
    # Load bearing: workers are spawned and re-import __main__. Without the
    # guard, opening a space forks forever.
    main()
