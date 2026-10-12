"""``nuspace init``: make a directory a space, without opening it to run.

The store only, through :func:`~nuspace.host.init_space`: the two SQLite
files and the system planes, seeded as the first open would. No venv, no
packaging: the directory is not set up for code of its own yet.
"""

from __future__ import annotations

from pathlib import Path

import rich_click as click
from rich.text import Text

import nu
from nu._branding import BLUE, PURPLE
from nuspace.host import init_space
from nuspace.system.kernel import KERNEL_FILE

from .._meta import STORE_ENV, console, opened


__all__ = ["init"]


@click.command(
    short_help="Make a directory a space, without running it.",
    help=(
        "Make PATH a space: its store and system planes, nothing run. PATH from"
        f" ${STORE_ENV}, the current directory without one. The store only for now:"
        " no venv or packaging is set up."
    ),
)
@click.argument("path", required=False, envvar=STORE_ENV, default=".")
def init(path: str) -> None:
    """Make the space, or say it already is one."""
    root = Path(path).expanduser().resolve()
    there = (root / KERNEL_FILE).exists()
    term = opened(init_space, str(root))
    nu.eval_in_loop(nu.compile(term), nu.Context())
    what = "Already a space" if there else "Initialized a space"
    console.print(Text.assemble((what, f"bold {PURPLE}"), ("  ", ""), (str(root), BLUE)))
    console.print(Text.assemble(("open it with: ", "dim"), (f"nuspace run {path}", f"bold {BLUE}")))
