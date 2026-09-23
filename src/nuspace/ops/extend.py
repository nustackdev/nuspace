"""Extension ops: run an app, insert a snippet.

Apps and snippets are registry entries, registered by the host at open.
Core ships none privileged: a third party registers the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .cell import add_cell


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu


__all__ = ["App", "Snippet", "insert_snippet", "run_app"]


@dataclass(frozen=True)
class App:
    """Something ``+`` makes: a Nu tree over ops, built on demand.

    Args:
        name: registry key.
        label: what the picker shows.
        build: ``build(**kwargs) -> Nu``, the tree to run. Makes a plane,
            linked planes, anything the ops allow.
        section: whether the sidebar lists a section for what it made.
        description: one line for the picker.
    """

    name: str
    label: str
    build: Callable[..., nu.Nu]
    section: bool = True
    description: str = ""


@dataclass(frozen=True)
class Snippet:
    """Source for one cell, offered from the ``/`` menu.

    Args:
        name: registry key, and the new cell's name.
        label: what the menu shows.
        source: the cell's prog.
    """

    name: str
    label: str
    source: str


def run_app(app: App, **kwargs: object) -> nu.Nu:
    """The app's tree, built with ``kwargs``. Evaluate it to run the app."""
    return app.build(**kwargs)


def insert_snippet(
    plane_id: nu.StrArg,
    snippet: Snippet,
    *,
    index: nu.IntArg | None = None,
    cell_id: nu.StrArg | None = None,
) -> nu.Nu:
    """Add a cell from a snippet: its source as the prog, its name as the name.

    Yields:
        The cell id, as :func:`~nuspace.ops.cell.add_cell` does.
    """
    return add_cell(plane_id, snippet.source, cell_id=cell_id, name=snippet.name, index=index)
