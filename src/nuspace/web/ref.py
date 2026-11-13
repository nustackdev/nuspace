"""The tab's own node on the browser's tree beside the sidebar and the viewer: its toaster.

A failed interaction shows here (:meth:`~nuspace.web.utils.Arms.event`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nuspace.web.utils import SpaceRef, toast


if TYPE_CHECKING:
    from nu.lang import Nu, StrArg


__all__ = ["ToastRef"]


class ToastRef(SpaceRef):
    """Where a tab shows toasts: the ui-kit's toaster, one per tab.

    Written by :func:`~nuspace.web.utils.toast` only.
    """

    _wire_type: ClassVar[str] = "ToastRef"

    def show(self, kind: StrArg, message: StrArg) -> Nu:
        """Show a toast: ``kind`` as its title, ``message`` under it."""
        return toast(self, kind, message)
