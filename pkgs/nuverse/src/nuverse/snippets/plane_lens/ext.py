"""The plane lens snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "plane_lens",
    "Plane lens",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="Browses the plane the cell sits on as cascading columns.",
    group="Debugging",
    icon="layers",
)
