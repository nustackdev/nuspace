"""A lens: browses a shape as cascading columns. Point SHAPE and PREFIX elsewhere to browse something else."""

import nuspace
from nuverse.snippets.lens import snippet


# SHAPE is a shape class: what the lens expects to find.
# PREFIX is a ref: where in the store that shape lives. None means the root.
#
# One plane, for example:
#   SHAPE = nuspace.shapes.Plane
#   PREFIX = nuspace.Space.planes["home"]
SHAPE = nuspace.Space
PREFIX = None


out = snippet.out(SHAPE, PREFIX)
