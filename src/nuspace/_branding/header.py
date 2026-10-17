"""The nuspace header, in three sizes.

- ``sm``: one line, the name and version, then where the space lives. What
  the command prints when a space opens.
- ``md``: the mark, with the name, version, tagline and where beside it.
- ``lg``: the same as ``md`` for now.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from rich.table import Table
from rich.text import Text

from .logo import logo
from .palette import BLUE, PURPLE


if TYPE_CHECKING:
    from rich.console import RenderableType


__all__ = ["TAGLINE", "header"]


#: What nuspace is, in a line.
TAGLINE = "a space of planes of cells, and the system that runs them"


def header(size: Literal["sm", "md", "lg"] = "sm", *, version: str, where: str) -> RenderableType:
    """The header at ``size``, for ``version`` and the space at ``where``."""
    name = Text.assemble(("nuspace ", f"bold {PURPLE}"), (version, BLUE))
    if size == "sm":
        return Text.assemble(name, ("  ", ""), (where, "dim"))
    side = Text("\n").join([name, Text(TAGLINE), Text(""), Text(where, style="dim")])
    grid = Table.grid(padding=(1, 4, 1, 0))
    grid.add_column()
    grid.add_column(vertical="middle")
    grid.add_row(logo(), side)
    return grid
