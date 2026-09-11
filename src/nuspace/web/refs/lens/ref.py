"""LensRef -- the wire handle for the Lens surface.

A pure handle, like ``PagesRef``. Configured once with the root Shape
class to browse and a row cap, stamped into the payload in ``__init__``
because Nu tree rewrites share the payload object and a later write would
bleed across them.

The browser owns the cursor. There is no server-side path: every notify
carries the full new path and the server recomputes the whole cascade for
it. Reload starts back at root, which is a choice rather than an
accident -- persisting the cursor means backing it with a fabric, and
that is a v2 call.

## Wire

Server -> browser, ``write`` frames on this ref's path. One shape, no
``op`` key: the lens ships its whole state every time.

    {"path": [str], "columns": [Column]}

    Column = {"kind": "shape"|"mapping"|"sequence"|"leaf",
              "entries": [Entry], "total": int}
    Entry  = {"key": str, "kind": str, "preview": str, "navigable": bool,
              "vtype": str, "text": str?, "clipped": bool?}

``kind`` is the *structural* kind -- which column shape the row leads to.
``vtype`` is the *value* type of what the row holds, so the browser can
tell an int from a string from an empty slot without reparsing a repr.
``text`` / ``clipped`` ride on leaf rows only: ``preview`` is a 120-char
cell repr and the leaf column renders the value in full.

Browser -> server, one ``notify`` on ``<this ref>.ops.nav``:

    {"path": [str]}

The op table is in ``ops.py``.

``max_rows`` rides in mount props as well as in python, so the TS slice
can seed and cap its own buffers. That is why this ref overrides
``SurfaceRef.slot``, which ships no props at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from typing_extensions import Self

import nu
from nuspace.web.refs.common import SurfaceRef


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.ui.core import Ref


__all__ = ["DEFAULT_MAX_ROWS", "LensRef"]


DEFAULT_MAX_ROWS = 200


class LensRef(SurfaceRef):
    """A browsable window onto a Nu Shape, as cascading Miller columns."""

    def __init__(
        self,
        address: object,
        *,
        parent_ref: Ref | None = None,
        owner_shape: type[Shape] | None = None,
        root_shape: type[Shape] | None = None,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> None:
        super().__init__(address, parent_ref=parent_ref, owner_shape=owner_shape)
        self._payload["lens_root"] = root_shape
        self._payload["lens_max_rows"] = int(max_rows)

    @classmethod
    def slot(cls, *, root: type[Shape], max_rows: int = DEFAULT_MAX_ROWS) -> Self:
        """Pin the root Shape class python-side and the cap on both sides."""
        return nu.Slot(  # type: ignore[return-value]
            cls,
            props={"max_rows": int(max_rows)},
            root_shape=root,
            max_rows=int(max_rows),
        )

    @property
    def root(self) -> Any:  # noqa: ANN401 -- a Shape class
        """The Shape class the lens browses. Required by ``slot()``."""
        root = self._payload.get("lens_root")
        if root is None:
            raise RuntimeError("LensRef.slot(root=...) requires a Shape class")
        return root

    @property
    def max_rows(self) -> int:
        """How many rows a column ships before it says ``total`` instead."""
        return int(self._payload.get("lens_max_rows", DEFAULT_MAX_ROWS))
