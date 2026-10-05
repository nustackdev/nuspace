"""A lens on one cell of this plane, picked from a dropdown. Point the shape and the prefix elsewhere to browse something else of it."""

import nu
import nuspace
from nuverse.snippets.cell_lens import snippet


def out(plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """The cell lens snippet's dropdown and browser."""
    # The shape: what the lens expects to find. The prefix, given the picked
    # cell's id: where in the store it lives. Here, the picked cell.
    return snippet.out(
        plane,
        cell,
        nuspace.shapes.Cell,
        lambda picked: nuspace.Space.cells[picked],
    )
