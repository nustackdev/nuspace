"""A lens on this plane. Point the shape and the prefix elsewhere to browse something else."""

import nuspace
from nuspace import ops
from nuverse.snippets.lens import snippet


# The shape: what the lens expects to find. The prefix: where in the store
# it lives. Here, this plane.
out = snippet.out(nuspace.shapes.Plane, nuspace.Space.planes[ops.Here.plane])
