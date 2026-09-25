"""The ``plane_lens`` snippet: a lens on the plane the cell sits on.

Edit ``SHAPE`` and ``PREFIX`` inside ``out`` to point it elsewhere.
"""

from __future__ import annotations

from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


SOURCE = """\
import nustd.ui.lens
import nuspace


def out(plane):
    # SHAPE is a shape class: what the lens expects to find.
    # PREFIX is a ref: where in the store that shape lives. Here, this plane.
    SHAPE = nuspace.shapes.Plane
    PREFIX = nuspace.Space.planes[plane]

    lens = nustd.ui.lens.LensRef("lens")
    return nustd.ui.lens.browse(lens, SHAPE, prefix=PREFIX)
"""

SNIPPET = Snippet("plane_lens", "Plane lens", SOURCE)
