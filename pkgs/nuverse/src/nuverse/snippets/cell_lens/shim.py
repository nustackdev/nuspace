"""A lens on one cell of this plane, picked from a dropdown. Point the shape and the prefix elsewhere to browse something else of it."""

import nuspace
from nuspace import ops
from nuverse.snippets.cell_lens import snippet


# The shape: what the lens expects to find. The prefix, given the picked
# cell's id: where in the store it lives. Here, the picked cell.
out = snippet.out(
    ops.Here.plane,
    ops.Here.cell,
    nuspace.shapes.Cell,
    lambda picked: nuspace.Space.cells[picked],
)
