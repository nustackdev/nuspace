"""The ``lens`` snippet: a cell that browses a shape as cascading columns.

Edit ``SHAPE`` and ``PREFIX`` at the top of the cell to point it elsewhere.
"""

from __future__ import annotations

from nuspace import Snippet


__all__ = ["SNIPPET", "SOURCE"]


SOURCE = """\
import nustd.ui.lens
import nuspace

# SHAPE is a shape class: what the lens expects to find.
# PREFIX is a ref: where in the store that shape lives. None means the root.
#
# One plane, for example:
#   SHAPE = nuspace.shapes.Plane
#   PREFIX = nuspace.Space.planes["home"]
SHAPE = nuspace.Space
PREFIX = None


def out():
    lens = nustd.ui.lens.LensRef("lens")
    return nustd.ui.lens.browse(lens, SHAPE, prefix=PREFIX)
"""

SNIPPET = Snippet("lens", "Lens", SOURCE)
