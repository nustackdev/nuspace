"""The text snippet, registered: the shim as its source, searchable by its text."""

from __future__ import annotations

from importlib import resources

from nuspace import TEXT, Snippet

from .ops import search, set_text, text_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    TEXT,
    "Text",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    search=search,
    description="Text a person reads and edits, markdown kept in the cell's state.",
    ops=(set_text, text_of),
    group="Content",
    icon="type",
)
