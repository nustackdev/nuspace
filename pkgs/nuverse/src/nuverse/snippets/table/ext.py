"""The table snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "table",
    "Table",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="An editable data table, rows and columns kept in the cell's state.",
    group="Content",
    icon="table",
)
