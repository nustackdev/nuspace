"""The cell lens snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "cell_lens",
    "Cell lens",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="Browses one cell of this plane, picked from a dropdown.",
)
