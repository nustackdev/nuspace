"""The lens snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "lens",
    "Lens",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="Browses the whole space, or any shape in it, as cascading columns.",
    group="Debugging",
    icon="scan-search",
)
