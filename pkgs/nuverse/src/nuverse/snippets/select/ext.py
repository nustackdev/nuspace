"""The select snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet

from .ops import search, set_value, value_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "select",
    "Select",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="One option of a list kept in the cell's state, its options under Config.",
    search=search,
    ops=(set_value, value_of),
    group="Inputs",
    icon="list",
)
