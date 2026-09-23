"""A space in a browser: pick a plane in the sidebar and its cells run.

Everything offered comes from nuverse, found through its entry point: the
``page`` app is a sidebar section, ``+`` makes a plane under it, and ``/``
offers its snippets, each a cell like any other: ``prose``, a text editor,
``program``, a starter to write code into, and ``ticker``. A Counter plane, a page with one ticker, is
seeded the first time. Selecting it is what brings it up (the nav service),
and leaving it takes it down again, which the count says out loud by going on
from where it stopped.

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
from nuspace import ops
from nuverse.apps.page import page
from nuverse.snippets import ticker


# Closing the space drops sockets under workers still holding them, and the
# transport logs each one. Expected. At module scope so spawned workers, which
# import this file, are quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


STORE = str(Path(__file__).parent / "v4.db")
PORT = int(os.environ.get("NUSPACE_PORT", "8080"))

COUNTER, TICK = "counter", "tick"


def seed() -> nu.Nu:
    """The Counter plane, the first time only: a later run keeps what was edited."""
    made = page(COUNTER, "Counter") >> ops.add_cell(COUNTER, ticker.SOURCE, cell_id=TICK, name=TICK)
    missing = nustd.kv.Snapshot(nu.Not(ops.plane_exists(COUNTER)), scope=nuspace.Space)
    return nu.IfDo(missing, made)


def main() -> None:
    print(f"nuspace web example   {STORE}")
    try:
        nu.run_in_loop(
            nuspace.open_space(
                STORE,
                port=PORT,
                # No apps or snippets here: nuverse is installed with nuspace
                # and found through its entry point, as any extension is. The
                # body never ends: the space is up until Ctrl+C.
                body=seed() >> nu.ForeverDo(nu.Delay(3600)),
            )
        )
    except KeyboardInterrupt:
        print("stopped")


if __name__ == "__main__":
    # Load bearing: workers are spawned and re-import __main__. Without the
    # guard, opening a space forks forever.
    main()
