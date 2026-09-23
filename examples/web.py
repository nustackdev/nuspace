"""A space in a browser: pick a plane in the sidebar and its cells run.

One app, ``page``, is a sidebar section: ``+`` makes a plane under it. Three
snippets are offered from ``/``: ``prose``, a document cell, ``program``, a
starter to write code into, and ``ticker``. A Counter plane is seeded the
first time. Selecting it is what brings it up (the nav service), and leaving
it takes it down again, which the count says out loud by going on from where
it stopped.

The store is ``examples/v4.db``, kept between runs.

Run it::

    python examples/web.py

A browser opens on http://127.0.0.1:8080. Ctrl+C stops it.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import nu
import nuspace
import nustd.kv
from nuspace import App, Snippet, ops


# Closing the space drops sockets under workers still holding them, and the
# transport logs each one. Expected. At module scope so spawned workers, which
# import this file, are quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


STORE = str(Path(__file__).parent / "v4.db")
PORT = int(os.environ.get("NUSPACE_PORT", "8080"))

COUNTER, TICK = "counter", "tick"

#: A cell that draws: one stat tile, and a count kept in its own state.
TICKER = """\
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


#: A document cell: one prose surface over a string in its own state, synced
#: both ways. Every prose cell holds exactly this prog, and that is how the
#: viewer tells one apart: what the person wrote lives in the state, not here.
PROSE = """\
import nu
import nustd.kv
import nustd.ui
import nuspace


class Doc(nuspace.CellState):
    text = nustd.kv.StrRef.slot()


def out():
    body = nustd.ui.ProseRef("text")
    held = nu.If(Doc.text.exists(), nu.ToStr(Doc.text), nu.Str(""))
    return (
        body.set(held)
        >> body.set_placeholder(nu.Str("Write, or press / for blocks"))
        >> nu.ParallelAsync(
            # This tab typed: keep it. Every other tab on the plane hears it
            # through the store.
            nu.ReactForever(body.on_change(), Doc.text.set(nu.Str(body))),
            # Somebody else typed: show it. The echo back to the author is a
            # no-op, the text is already what it says.
            nu.ReactForever(Doc.text.on_change(), body.set(nu.ToStr(Doc.text))),
        )
    )
"""

#: What a fresh code cell starts as: one key in its own state, then done.
PROGRAM = """\
import nu
import nustd.kv
import nuspace


class Note(nuspace.CellState):
    hello = nustd.kv.StrRef.slot()


def out():
    # Bare state: the kernel lands it under this cell, whichever it is.
    return Note.hello.set(nu.Str("world"))
"""


def page(plane_id: nu.StrArg | None = None, name: nu.StrArg = "") -> nu.Nu:
    """The ``page`` app: a plane the sidebar lists under Pages."""
    return ops.add_plane(
        plane_id, name=name, meta={"ui": True, "made_by": "page", "editable": True}
    )


APPS = [App("page", "Pages", page, description="A plane of cells.")]
SNIPPETS = [
    Snippet("prose", "Text", PROSE),
    Snippet("program", "Program", PROGRAM),
    Snippet("ticker", "Ticker", TICKER),
]


def seed() -> nu.Nu:
    """The Counter plane, the first time only: a later run keeps what was edited."""
    made = page(COUNTER, "Counter") >> ops.add_cell(COUNTER, TICKER, cell_id=TICK, name=TICK)
    missing = nustd.kv.Snapshot(nu.Not(ops.plane_exists(COUNTER)), scope=nuspace.Space)
    return nu.IfDo(missing, made)


def main() -> None:
    print(f"nuspace web example   {STORE}")
    try:
        nu.run_in_loop(
            nuspace.open_space(
                STORE,
                port=PORT,
                apps=APPS,
                snippets=SNIPPETS,
                # The body never ends: the space is up until Ctrl+C.
                body=seed() >> nu.ForeverDo(nu.Delay(3600)),
            )
        )
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    # Load bearing: workers are spawned and re-import __main__. Without the
    # guard, opening a space forks forever.
    main()
