"""What the live apps share: a listed page, made with its cells already on it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import binding


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = ["live_page", "meta"]


def meta(app: str) -> dict[str, object]:
    """The meta a section app marks its planes with: drawn, listed under ``app``, editable."""
    return {"ui": True, "made_by": app, "editable": True}


def live_page(
    app: str,
    plane_id: nu.StrArg | None,
    name: nu.StrArg,
    cells: Sequence[tuple[str, str]],
) -> nu.Nu:
    """A plane for section ``app``, then one cell per ``(name, source)``.

    Yields:
        The plane id, as :func:`~nuspace.ops.add_plane` does.
    """

    def fill(pid: str) -> nu.Nu:
        return nu.Sequential(
            *(ops.add_cell(nu.StrAttrRef(pid), source, name=cell) for cell, source in cells)
        )

    return binding(ops.add_plane(plane_id, name=name, meta=meta(app)), fill, tag="live")
