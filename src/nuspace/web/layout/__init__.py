"""The plane layout: how a web plane arranges its cells, rows of single cells or strips of columns.

``Web.planes[plane].layout`` sits beside ``Plane.cells``, not instead of it:
``cells`` says which cells are on the plane, the layout how the web draws
them. Same structure and wording as a desk's items (:mod:`nuspace.web.desks`):
an ordered dict of item id to item, each a cell item ``{kind: "cell", cell}``
or a strip ``{kind: "strip", columns: [{cells, share}]}``, its columns side
by side at their shares, the cells of a column stacked.

**Fixed up when read, never synced.** No reaction keeps the layout in step
with ``cells``. The read (:func:`~.model.layout_view`) skips a cell no
longer on the plane (removed or transferred out), and its stored item stays,
so a restored cell comes back where it was. Then the strip rules, as desks
prune: an empty column goes, the shares left rescale, a strip left with one
cell reads as a cell item, an empty strip goes. A cell on the plane in no
item shows as its own cell item right after the item holding the cell before
it in ``cells`` order, at the top when nothing is before it. An empty or
missing layout is one cell item per cell, in ``cells`` order.

**Every op fills first.** Each op stores the items the read showed and the
store lacks, at the read's spots and ids, then makes its own change: an item
the browser saw is always there to anchor on.

``ops``
    The layout ops a program calls, re-exported here::

        import nuspace.web as web

        nuspace.atomic(web.layout.move_item(plane, item_id, before=other))

``model``
    The layout shape in plain python, the fix-up, and the hosts running them.

The pane ships the fixed-up layout with its cells, and hears one event per
op (:mod:`nuspace.web.viewer.feed`). On a web plane the browser's reorder
writes the layout (``move_item``), not ``cell.move``, which stays for
non-web and headless use.
"""

from nuspace.web.layout.ops import (
    add_item,
    get_layout,
    move_item,
    place_cell,
    remove_item,
    set_item,
    transfer_cell,
    write_items,
)


__all__ = [
    "add_item",
    "get_layout",
    "move_item",
    "place_cell",
    "remove_item",
    "set_item",
    "transfer_cell",
    "write_items",
]
