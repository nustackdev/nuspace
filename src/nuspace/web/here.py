"""What a cell on a web pane reaches of its own pane: :func:`pane`.

A cell's run is its tab's own (nav adds one plane run per pane per tab, its
session env bound to the tab), so the pane for ``Here.plane`` under the
shell's viewer is this tab's pane on this plane, with no lookup::

    import nuspace.web as web

    web.pane().follow("bottom")     # stay at the end as the cell appends
    web.pane().scroll("top")        # once
    web.pane().scroll_to(Here.cell)

The ref is rooted on the viewer, a nuspace region, so the session env's
rewrite leaves it where it is instead of landing it under the cell.

Kept out of :mod:`.ops`: those are store ops, this builds a browser ref.
Safe for a worker to import: it pulls in no server.
"""

from __future__ import annotations

from nuspace.places import Here

from .shell import Shell
from .viewer.ref import PaneRef, pane_ref


__all__ = ["pane"]


def pane() -> PaneRef:
    """The running cell's pane: its plane's pane on the tab the run draws on.

    Its writes reach only that tab: a run on no tab has no session and
    raises when one runs. Cost: O(1) to build, nothing read.

    Raises:
        LookupError: Run outside a cell run, where no Here is bound.
    """
    return pane_ref(Shell.viewer, Here.plane)
