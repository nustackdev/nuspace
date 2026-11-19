"""A space in the browser, with whatever extensions are installed, run by the local assembly.

Every Plane, Cell and content kind comes from an installed extension, found
through its entry point.
The space's root is ``examples/example.nuspace``, its data in ``.nuspace/``
inside it, kept between runs. ``local.init`` initializes it, a no-op once
done; ``local.run`` then holds its infra here, runs its kernel and its
web as two workers of one process pool, and starts web again if it stops.
``open.py`` beside it reaches the same space from a script.

Run it::

    uv run python examples/space.py

A browser opens on http://127.0.0.1:8080. Ctrl+C stops both.
"""

from __future__ import annotations

from pathlib import Path

import nu
from nuspace.space import local


STORE = str(Path(__file__).parent / "example.nuspace")


if __name__ == "__main__":
    # The drivers run in workers of their own; this process holds infra and watches them.
    try:
        nu.run_in_loop(local.init(STORE))
        nu.run_in_loop(local.run(STORE))
    except KeyboardInterrupt:
        print("stopped")
