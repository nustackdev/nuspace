"""A space's stores from a script, with no kernel and no web: ``local.open`` around a body of ops.

What a script or an agent uses to read and change a space, running or not.
The same space as ``space.py`` (``examples/example.nuspace``): it makes a
plane, then lists every plane the space holds. Run it with nothing up and it
only writes the files; run it beside ``space.py`` and the kernel and web hear
the write, so the new plane shows in the browser.

Run it::

    uv run python examples/open.py

``open`` yields nothing, like every entry point: what the body wants to keep
it prints here, or writes into a ref the caller holds.
"""

from __future__ import annotations

from pathlib import Path

import nu
import nuspace
from nuspace.shapes import Space
from nuspace.space import local


STORE = str(Path(__file__).parent / "example.nuspace")


def made(plane: nu.ObjectRef) -> nu.Nu:
    """A plane made in one commit, its minted id in ``plane``."""
    return nuspace.atomic(nuspace.plane.add(name="From a script", backend="async", into=plane))


#: Every plane's id and name, one per line, read from one snapshot.
listed = nuspace.atomic(
    nu.ForEachDo(
        Space.planes.keys(),
        lambda plane: nu.print(" ", plane, Space.planes[plane].name),
    )
)


if __name__ == "__main__":
    nu.run_in_loop(local.init(STORE))
    nu.run_in_loop(
        local.open(
            STORE,
            body=nu.let(lambda x: made(x) >> nu.print("added plane: ", nu.str(x)), x="")
            >> nu.print("planes:")
            >> listed,
        )
    )
