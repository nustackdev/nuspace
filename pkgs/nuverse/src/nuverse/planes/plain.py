"""The ``plain`` Plane: no cells, no children. First in the picker.

Not special, just first. A plain plane with nothing on it also works as a
folder: grouping in the sidebar is nesting.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["PLANE"]


PLANE = Plane(
    "plain",
    "Plain",
    description="An empty plane. Add cells with /, or nest planes under it.",
    meta={"editable": True, "full_width": False},
)
