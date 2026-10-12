"""``nuspace demo``: list the demos, or open one in a space.

The demos are the Planes ``nuverse-demos`` registers, an optional extra
(``nuspace[demos]``). Installed, it registers them for ``+`` in every space
too; this command opens one straight away through the
:func:`~nuspace.host.demo` preset. The space is a throwaway one unless PATH
is given, and not ``$NUSPACE_STORE``: a demo never lands in your space
unless you name it.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import rich_click as click
from rich.table import Table
from rich.text import Text

from nu._branding import BLUE, PURPLE
from nuspace.host import presets

from .._meta import announce, console, hold, opened


if TYPE_CHECKING:
    from nuspace.ext import Plane


__all__ = ["INSTALL_HINT", "demo", "demos"]


#: What to run when the demos are not installed.
INSTALL_HINT = 'pip install "nuspace[demos]"'


def demos() -> dict[str, Plane] | None:
    """The demo Planes by name, in the order registered. None when the extra is missing."""
    try:
        from nuverse_demos import extension
    except ImportError:
        return None
    return {spec.name: spec for spec in extension().planes}


def _missing() -> None:
    console.print("[yellow]The demos are not installed.[/yellow]")
    console.print(Text.assemble(("install with: ", "dim"), (INSTALL_HINT, f"bold {BLUE}")))
    sys.exit(1)


def _list(found: dict[str, Plane]) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style=f"bold {BLUE}")
    table.add_column(style="dim")
    for name, spec in found.items():
        table.add_row(name, spec.description)
    console.print(Text("demos", style=f"bold {PURPLE}"))
    console.print(table)
    console.print(
        Text.assemble(("open one with: ", "dim"), ("nuspace demo <name>", f"bold {BLUE}"))
    )


@click.command(
    short_help="List the demos, or open one in a space.",
    help=(
        "List the demos, or open the one named NAME in a space: a throwaway one,"
        f" or PATH. Needs the demos extra: {INSTALL_HINT}"
    ),
)
@click.argument("name", required=False)
@click.argument("path", required=False)
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("-p", "--port", default=8080, show_default=True, help="Port to bind.")
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab on the way up.")
def demo(name: str | None, path: str | None, host: str, port: int, no_browser: bool) -> None:
    """No name: list. A name: serve that demo until Ctrl+C."""
    found = demos()
    if found is None:
        _missing()
        return
    if name is None:
        _list(found)
        return
    if name not in found:
        console.print(f"[red]Unknown demo:[/red] [bold]{name}[/bold]", highlight=False)
        console.print(Text.assemble(("available: ", "dim"), (", ".join(found) or "(none)", BLUE)))
        sys.exit(2)
    spec = found[name]
    term = opened(presets.demo, spec, path, host=host, port=port, open_browser=not no_browser)
    announce(path, f"http://{host}:{port}/{presets.demo_id(spec)}")
    hold(term)
