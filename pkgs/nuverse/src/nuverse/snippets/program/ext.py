"""The program snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "program",
    "Program",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="A code cell that writes one key in its own state and ends.",
)
