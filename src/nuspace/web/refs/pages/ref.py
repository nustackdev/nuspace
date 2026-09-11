"""PagesRef -- the wire handle for the Pages surface.

A pure handle. Configured once with the ``space_root`` Shape class whose
``.pages`` slot is the root ``Page``, and stamped into the payload in
``__init__`` because Nu tree rewrites share the payload object and a
later write would bleed across them.

The browser owns the cursor (the URL), per-block edit mode, caret,
selection and unsaved buffers. The server owns the page tree, the active
page payload and section status.

## Wire

Server -> browser, all ``write`` frames on this ref's path, dispatched by
the browser slice on ``payload["op"]``:

    {"op": "set_tree",   "tree": PageNode}
    {"op": "set_page",   "page_id": str|None, "path": [str], "title": str,
                         "blocks": [Block]}
    {"op": "set_status", "statuses": [Status]}

    PageNode = {"id": str|None, "title": str, "pages": [PageNode]}
    Block    = {"id", "kind": "prose"|"program", "source", "order": int,
                "fields": [MountField], "status": Status|None}
    Status   = the section status contract. It is not restated per
               surface -- ``nuspace.exec.status`` is its one home.

Browser -> server, one ``notify`` per op, each on its own path
``<this ref>.ops.<op>``, payload = the op's named arguments and nothing
else. The op list is in ``ops.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nuspace.web.refs.common import SurfaceRef


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.ui.core import Ref


__all__ = ["PagesRef"]


class PagesRef(SurfaceRef):
    """Nested page tree + per-page block canvas over a Space's page root."""

    def __init__(
        self,
        address: object,
        *,
        parent_ref: Ref | None = None,
        owner_shape: type[Shape] | None = None,
        space_root: type[Shape] | None = None,
    ) -> None:
        super().__init__(address, parent_ref=parent_ref, owner_shape=owner_shape)
        self._payload["pages_space_root"] = space_root

    @property
    def space_root(self) -> Any:  # noqa: ANN401 -- a Shape class
        """The Shape class the driver walks. Required by ``slot()``."""
        root = self._payload.get("pages_space_root")
        if root is None:
            raise RuntimeError("PagesRef.slot(space_root=...) requires a Shape class")
        return root
