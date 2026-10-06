"""The number snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet

from .ops import set_value, value_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "number",
    "Number",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="A number kept in the cell's state, with its bounds and step under Config.",
    ops=(set_value, value_of),
    group="Inputs",
    icon="hash",
)
