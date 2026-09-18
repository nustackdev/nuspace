"""A Space in a browser, where opening a Plane is what starts it.

Everything phase 2 claims, in a tab rather than in a print:

- the sidebar lists every Plane that draws, under one row for the Space;
- clicking one selects it, and selecting it is what brings its Cells up;
- a Cell draws under its own node on the page, from the worker it runs in;
- navigating away takes that worker down, and navigating back brings it up
  again, which the counter says out loud by starting from where it left off;
- prose is a Cell like any other: it holds a program that draws an editor.

Two Planes are seeded the first time and nothing after that, so what you write
is still there next time.

Run it::

    python examples/web.py

A browser opens on http://127.0.0.1:8080. Pick Notes and type. Pick
Counter and watch it climb, then pick Notes again and come back to it: the
seconds are not the ones that went by while you were away, because nothing was
running while nobody was looking.

Ctrl+C stops it. The Space is left on disk, so `nuspace -s <path> ls` reads
what it did.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import nu
import nustd.kv
from nuspace import EXEC_ASYNC, TRIGGER_NAV, Space, ops, presets, store
from nuspace.web.viewer import prose_source


# Closing the Space drops the sockets under workers that are still holding
# them, and the transport logs every one of those. Expected, and the only thing
# this demo has to say is what it drew. At module scope so a spawned worker,
# which imports this file, is quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


#: Kept between runs, because the point of a page is that what you wrote is
#: still on it tomorrow.
STORE = Path(tempfile.gettempdir()) / "nuspace-web-demo"

PORT = 8080

NOTES, COUNTER = "p_notes", "p_counter"
TEXT, TICK = "s_text", "s_tick"


#: A Cell that draws. One stat tile and a loop, and it says nothing about where
#: the tile lives: the ref is written bare and the host roots it under this
#: Cell's own node on whatever surface the Plane is drawn on.
TICKER = '''import nu
import nustd.kv
import nustd.ui
from nuspace import Space


def out(plane, cell):
    """Count seconds, in the browser and in this Cell's own state."""
    tile = nustd.ui.StatRef("seconds")
    state = Space.planes[plane].cells[cell].state
    now = nu.Int(nu.ToInt(state.get_item("ticks", nu.Int(0))))
    step = state.set_item("ticks", now + nu.Int(1)) >> tile.set_value(
        nu.ToStr(now + nu.Int(1))
    )
    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(
        tile.set_label(nu.Str("seconds this Plane has been open"))
        >> nu.ForeverDo(nu.DelayedDo(nu.Float(1.0), step)),
        scope=Space,
    )
'''


def plane(plane_id, name):
    """One Plane a tab can navigate to, drawn as a page."""
    return ops.add_plane(
        plane_id=plane_id,
        name=name,
        exec_mode=EXEC_ASYNC,
        # Up because somebody is looking at it, and down again when they stop.
        trigger=TRIGGER_NAV,
        ui=True,
        editable=True,
    )


def seed():
    """Two Planes, once. A Space that already has one is left alone.

    Guarded rather than made idempotent: adding a Cell rewrites the row, so
    seeding on every run would put the empty page back over whatever the last
    run wrote on it.
    """
    made = (
        plane(NOTES, "Notes")
        >> ops.add_cell(NOTES, prose_source(Space), cell_id=TEXT, name=TEXT)
        >> plane(COUNTER, "Counter")
        >> ops.add_cell(COUNTER, TICKER, cell_id=TICK, name=TICK)
    )
    return nu.IfDo(nu.Eq(nu.Len(ops.plane_ids()), nu.Int(0)), made)


def main():
    STORE.mkdir(parents=True, exist_ok=True)
    print(f"\nnuspace web demo   {STORE}")
    print("  Notes     a page to write on")
    print("  Counter   a Cell that draws, and only while you are looking")
    # Seeded against a store this process then closes, because the Space the
    # server opens takes the write lock for as long as it is up.
    nu.run_in_loop(
        nu.With(store(str(STORE)), body=nustd.kv.auto_flow_atomic(seed(), scope=Space)),
        nu.Context(),
    )
    print(f"\n  http://127.0.0.1:{PORT}, Ctrl+C to stop\n")
    try:
        # max_parallel=1: nothing in the runtime computes, every branch is an
        # await, and a larger budget rations each arm against a semaphore those
        # arms never give back.
        nu.run_in_loop(
            presets.full(path=str(STORE), port=PORT),
            nu.Context(),
            max_parallel=1,
        )
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    # The guard is load bearing: the pool spawns, and a child re-imports
    # whatever __main__ is. Without it, opening a Space forks forever.
    main()
