"""The plane layout: how a web plane arranges its cells, rows of single cells or strips of columns.

``Plane.cells`` (Space) is membership: the cell belongs to the plane, its
order means nothing here. ``WebPlane.layout`` (Web) is the arrangement, one
plain value read and written whole, a list of rows:

- ``{kind: "cell", cell}``: a cell alone on its row;
- ``{kind: "strip", columns: [{cells, share}]}``: columns side by side at
  their shares (summing to 1), the cells of a column stacked.

No item ids: a row or a column is addressed by the cells in it.

**Eventually consistent with ``cells``, through two ops only.** The raw slot
is internal; :func:`get` and :func:`set` are the only readers and writers,
both plain kv terms around one pure host, :data:`~.model.LayoutReconcile`: cells
no longer on the plane dropped by the strip rules, a cell in two places kept
by its first holder, a cell in no row appended as its own row. No pruner,
no reaction.

- :func:`get`: the main read, heals the slot (0 or 1 write). Only the pane
  calls it, on open and on every reship, so one change is reconciled once
  per open plane. Code reading a layout calls it too; no op does.
- :func:`set`: every edit. The browser sends the whole new rows; they are
  checked on the shape and reconciled on the way in, so a stale view never
  writes a broken layout.
- :func:`transfer`: ``cell.transfer``, then :func:`set` on the target. Two
  commits, transfer first.

A cell made or removed with the core ops alone lands in the layout on the
next :func:`get`: an open pane on its reship, a closed plane when opened. A
cell that leaves is dropped for good: no old spot is kept. On a web plane
nothing uses ``cell.move``; it stays for non-web and headless use.

``model``
    The rows' shape check and the reconcile, plain python and their hosts.
``ops``
    :func:`get`, :func:`set`, :func:`transfer`.
"""

from nuspace.web.layout.ops import get, set, transfer


__all__ = ["get", "set", "transfer"]
