"""``nuspace init``: make a directory a space, without opening it to run.

The store only, through :func:`~nuspace.host.init_space`: ``.nuspace/``
with its two SQLite files and the system planes, seeded as the first open
would. Without PATH it is the current directory, said so when that sits
inside another space. No venv, no packaging: the directory is not set up
for code of its own yet.
"""

from __future__ import annotations

from pathlib import Path

import rich_click as click
from rich.text import Text

import nu
from nuspace._branding import BLUE, PURPLE
from nuspace.host import init_space
from nuspace.system.kernel import find_space, is_space

from .._meta import console, opened, path_argument, tilde


__all__ = ["init"]


@click.command(
    short_help="Make a directory a space, without running it.",
    help=(
        "Make PATH a space, the current directory without one: its data in .nuspace/,"
        " the system planes seeded, nothing run. No venv or packaging is set up yet."
    ),
)
@path_argument
def init(path: str | None) -> None:
    """Make the space, or say it already is one."""
    root = Path(path or ".").expanduser().resolve()
    if path is None:
        _warn_if_nested(root)
    there = is_space(root)
    term = opened(init_space, str(root))
    nu.eval_in_loop(nu.compile(term), nu.Context())
    what = "Already a space" if there else "Initialized a space"
    console.print(Text.assemble((what, f"bold {PURPLE}"), ("  ", ""), (tilde(root), BLUE)))
    again = "nuspace run" if path is None else f"nuspace run {path}"
    console.print(Text.assemble(("open it with: ", "dim"), (again, f"bold {BLUE}")))


def _warn_if_nested(root: Path) -> None:
    """Say so when ``root`` sits inside another space. The home space, everyone's fallback, does not count."""
    outer = find_space(root.parent) if root != root.parent else None
    if outer is not None and outer != Path.home().resolve():
        console.print(
            Text.assemble(
                ("inside the space at ", "yellow"),
                (tilde(outer), BLUE),
                (", making a new one here", "yellow"),
            )
        )
