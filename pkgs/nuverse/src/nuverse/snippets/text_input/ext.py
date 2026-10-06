"""The text input snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet

from .ops import set_value, value_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "text_input",
    "Text input",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="A line of text kept in the cell's state.",
    ops=(set_value, value_of),
    group="Inputs",
    icon="pen-tool",
)
