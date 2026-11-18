"""``nuspace init``: make a directory a space and initialize it, without running it.

The assembly's ``init`` (``local`` for a new space,
:func:`~nuspace._cli._meta.assembly`): ``.nuspace/`` with its stores, the
system planes and the web planes, then ``"init": true`` in its
``meta.json``. A plain ``nuspace run`` does the same before it runs; the
single component runs (``--infra``, ``--kernel``, ``--web``) need it done.
It runs again on a space already initialized, changing nothing, and is
refused while any of its components runs. Without PATH it is the current
directory, said so when that sits inside another space. No venv, no
packaging: the directory is not set up for code of its own yet.
"""

from __future__ import annotations

from pathlib import Path

import rich_click as click
from rich.text import Text

from nuspace._branding import BLUE, PURPLE

from .._meta import assembly, console, hold, initialized, nearest_space, path_argument, tilde


__all__ = ["init"]


@click.command(
    short_help="Make a directory a space and initialize it, without running it.",
    help=(
        "Make PATH a space and initialize it, the current directory without one: its data"
        " in .nuspace/, the system planes seeded, nothing run. Needed before run --infra,"
        " --kernel or --web; a plain run does it itself. No venv or packaging is set up yet."
    ),
)
@path_argument
def init(path: str | None) -> None:
    """Make and initialize the space, or say it already was."""
    root = Path(path or ".").expanduser().resolve()
    if path is None:
        _warn_if_nested(root)
    space = assembly(str(root))
    before = initialized(str(root))
    hold(space.init(str(root)))
    what = "Already initialized" if before else "Initialized a space"
    console.print(Text.assemble((what, f"bold {PURPLE}"), ("  ", ""), (tilde(root), BLUE)))
    again = "nuspace run" if path is None else f"nuspace run {path}"
    console.print(Text.assemble(("open it with: ", "dim"), (again, f"bold {BLUE}")))


def _warn_if_nested(root: Path) -> None:
    """Say so when ``root`` sits inside another space. The home space, everyone's fallback, does not count."""
    outer = nearest_space(root.parent) if root != root.parent else None
    if outer is not None and outer != Path.home().resolve():
        console.print(
            Text.assemble(
                ("inside the space at ", "yellow"),
                (tilde(outer), BLUE),
                (", making a new one here", "yellow"),
            )
        )
