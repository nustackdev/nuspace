"""The ``page`` app: a plane of cells the sidebar lists under Pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import App, ops


if TYPE_CHECKING:
    import nu


__all__ = ["APP", "page"]


#: What the page app marks its planes with: drawn, listed, editable.
META = {"ui": True, "made_by": "page", "editable": True}


def page(plane_id: nu.StrArg | None = None, name: nu.StrArg = "") -> nu.Nu:
    """A page plane. Yields its id, as :func:`~nuspace.ops.add_plane` does."""
    return ops.add_plane(plane_id, name=name, meta=META)


APP = App("page", "Pages", page, description="A plane of cells.")
