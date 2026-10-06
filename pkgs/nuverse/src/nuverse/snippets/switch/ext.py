"""The switch snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet

from .ops import search, set_value, value_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "switch",
    "Switch",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="An on or off kept in the cell's state.",
    search=search,
    ops=(set_value, value_of),
    group="Inputs",
    icon="square-check-big",
)
