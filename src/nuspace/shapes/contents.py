"""Contents: where every item of every kind lives, by kind, then scope, then id.

Part of the state store (:class:`~nuspace.shapes.states.States`), under
``contents``::

    States.contents             kind name -> KindContents
      <kind>
        cells    <cell id>  -> Items   {<id> -> the kind's Shape}
        planes   <plane id> -> Items
        space    Items

Kind first, so a search reads one kind's subtree and nothing else. A scope
is a typed level, so nothing parses a scope string. An item is never
slotted into a program's own state: it lives here, and only a
:class:`~nuspace.content.Content` reaches it, typed as its kind's Shape.

:class:`CellContent` and :class:`PlaneContent` are what a relative item
chain (``TextContent.cell("summary")``) is rooted at until the kernel lands
it under the running cell or plane (:mod:`nuspace.shapes.reroot`), as
``CellState`` and ``PlaneState`` are for state.
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["CONTENT_KIND", "CellContent", "Items", "KindContents", "PlaneContent"]


#: The payload key a relative item chain's root names its kind under.
CONTENT_KIND = "content_kind"


class Items(nu.Shape):
    """One scope's items of one kind, by id. No slots: the kind's Content types each item."""


class KindContents(nu.Shape):
    """One kind's items, one slot per scope: each cell's, each plane's, the space's."""

    cells = nustd.kv.DictRef.slot(Items)
    planes = nustd.kv.DictRef.slot(Items)
    space = nustd.kv.ShapeRef.slot(Items)


class CellContent(nu.Shape):
    """Root of a relative item chain of the running cell. Lands at ``contents[kind].cells[c]``."""


class PlaneContent(nu.Shape):
    """Root of a relative item chain of the running plane. Lands at ``contents[kind].planes[p]``."""
