"""The Pages interactions, one module per subject.

- ``page``  -- select, create, rename, delete, and the root-page init.
- ``block`` -- create, update, delete, split, merge, reorder, restart,
  and the ``renumber`` every structural change ends with.
- ``ship``  -- the three outbound loops (tree, page, status) and the kv
  subscription that feeds them.

Each body takes named arguments. The op path carries which interaction,
the payload carries only its arguments, so nothing here asks what op it
is or coerces a value out of a bag.
"""

from nuspace.web.refs.pages.interactions import ship
from nuspace.web.refs.pages.interactions.block import BlockOps
from nuspace.web.refs.pages.interactions.page import PageOps


__all__ = ["BlockOps", "PageOps", "ship"]
