"""The tab's own node on the browser's tree beside the sidebar and the viewer: its toaster.

A failed interaction shows here (:meth:`~nuspace.web.utils.Arms.event`).
The browser's own delete toasts carry an Undo, sent back on this node: it
lives as long as the tab, so an undo still lands after the pane that
deleted has gone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nuspace.web.utils import SpaceRef, event, toast


if TYPE_CHECKING:
    from nu.lang import Nu, StrArg
    from nustd.ui.core import Changed


__all__ = ["ToastRef"]


class ToastRef(SpaceRef):
    """Where a tab shows toasts: the ui-kit's toaster, one per tab.

    Written by :func:`~nuspace.web.utils.toast` only. Its events are the
    undos of a delete toast: ``plane.restore`` ``{plane_id}`` and
    ``cell.restore`` ``{cell_ids}``.
    """

    _wire_type: ClassVar[str] = "ToastRef"

    def show(self, kind: StrArg, message: StrArg) -> Nu:
        """Show a toast: ``kind`` as its title, ``message`` under it."""
        return toast(self, kind, message)

    def on_restore_plane(self) -> Changed:
        """``{plane_id}``: the Undo on a plane's delete toast."""
        return event(self, "plane.restore")

    def on_restore_cells(self) -> Changed:
        """``{cell_ids}``: the Undo on a delete toast for one cell or several."""
        return event(self, "cell.restore")
