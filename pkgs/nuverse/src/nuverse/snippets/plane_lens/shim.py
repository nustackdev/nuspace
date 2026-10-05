"""A lens on this plane. Point the shape and the prefix elsewhere to browse something else."""

import nu
import nuspace
from nuverse.snippets.lens import snippet


def out(plane: nu.StrArg) -> nu.Nu:
    """The lens snippet's browser, on this plane."""
    # The shape: what the lens expects to find. The prefix: where in the
    # store it lives. Here, this plane.
    return snippet.out(nuspace.shapes.Plane, nuspace.Space.planes[plane])
