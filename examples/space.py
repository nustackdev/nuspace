"""A space in the browser, with nuverse and nothing else.

Every Plane and snippet comes from nuverse, found through its entry point. The
space is the directory ``examples/example.nuspace``, kept between runs.

Run it::

    python examples/space.py

A browser opens on http://127.0.0.1:8080. Ctrl+C stops it.
"""

from __future__ import annotations

import logging
from pathlib import Path

import nu
import nuspace


# Closing the space drops sockets under workers still holding them. Expected.
# At module scope so spawned workers, which import this file, are quiet too.
logging.getLogger("invisibles").setLevel(logging.CRITICAL)


STORE = str(Path(__file__).parent / "example.nuspace")


if __name__ == "__main__":
    # Load bearing: workers are spawned and re-import __main__.
    try:
        nu.run_in_loop(nuspace.open_space(STORE))
    except KeyboardInterrupt:
        print("stopped")
