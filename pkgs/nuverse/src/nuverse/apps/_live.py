"""What the live apps share: a listed page, made with its cells already on it."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import binding


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = ["META", "live_page", "plane"]


#: What a section app's planes start with: editable, not full width.
META = {"editable": True, "full_width": False}


def plane(app: str, plane_id: nu.StrArg | None, name: nu.StrArg) -> nu.Nu:
    """A plane for section ``app``: drawn, listed under ``app``, editable.

    Yields:
        The plane id, as :func:`~nuspace.ops.add_plane` does.
    """
    return ops.add_plane(plane_id, name=name, ui=True, made_by=app, meta=META)


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

    return binding(plane(app, plane_id, name), fill, tag="live")
