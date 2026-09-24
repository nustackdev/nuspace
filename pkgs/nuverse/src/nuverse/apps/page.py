"""The ``page`` app: a plane of cells the sidebar lists under Pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import App

from ._live import plane


if TYPE_CHECKING:
    import nu


__all__ = ["APP", "page"]


def page(plane_id: nu.StrArg | None = None, name: nu.StrArg = "") -> nu.Nu:
    """A page plane. Yields its id, as :func:`~nuspace.ops.add_plane` does."""
    return plane("page", plane_id, name)


APP = App("page", "Pages", page, description="A plane of cells.")
