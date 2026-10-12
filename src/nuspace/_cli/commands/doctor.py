"""``nuspace doctor``: what this install holds, and what it lacks.

Probes only, nothing imported: a row is green when every module it names
resolves. Three parts:

- the runtime, what a space cannot open without: a missing row is a broken
  install;
- the extras, what ``nuspace[demos]`` and ``nuspace[all]`` add;
- the extensions installed under the ``nuspace.extensions`` entry points,
  which every space opened here registers.
"""

from __future__ import annotations

import importlib.util
import platform
import sys
from importlib.metadata import entry_points

import rich_click as click
from rich.table import Table
from rich.text import Text

from nu._branding import BLUE, PURPLE
from nuspace import _telemetry
from nuspace.ext.registry import GROUP

from .._meta import console, version_of


__all__ = ["doctor"]


#: What a space runs on, as ``(row, distribution, modules)``. Each comes with
#: ``pip install nuspace``, so a missing one is a broken install.
_RUNTIME: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("nustd", "nustd", ("nustd",)),
    ("store", "virtuals-py", ("virtuals",)),
    ("notifications", "valkeylite", ("valkeylite",)),
    ("workers", "invisibles-py", ("invisibles",)),
    ("web server", "starlette", ("starlette", "uvicorn", "websockets", "msgpack")),
    ("web bundle", "nuspace-ui", ("nuspace_ui",)),
)

#: The extras, as ``(row, extra, modules)``: the demos, then what ``all``
#: brings beyond the runtime, one row per nustd fabric.
_EXTRAS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("demos", "demos", ("nuverse_demos",)),
    ("cluster", "all", ("ray",)),
    ("http, llm", "all", ("httpx",)),
    ("queue", "all", ("janus",)),
    ("cc", "all", ("claude_agent_sdk",)),
)


def _resolves(modules: tuple[str, ...]) -> bool:
    return all(importlib.util.find_spec(m) is not None for m in modules)


def _table(*columns: str) -> Table:
    table = Table(show_header=True, header_style=f"bold {PURPLE}", box=None, padding=(0, 2))
    table.add_column(columns[0], style="bold")
    for column in columns[1:]:
        table.add_column(column)
    return table


@click.command(
    short_help="Check the install: versions, extras, extensions.",
    help="Report versions, the runtime, the extras and the installed extensions.",
)
def doctor() -> None:
    """Print what this install holds."""
    console.print(
        Text.assemble(
            ("nuspace ", f"bold {PURPLE}"),
            (version_of("nuspace"), f"bold {BLUE}"),
            ("  ·  nu ", "dim"),
            (version_of("nucore"), BLUE),
            ("  ·  python ", "dim"),
            (sys.version.split()[0], BLUE),
            ("  ·  ", "dim"),
            (f"{platform.system().lower()} {platform.machine().lower()}", BLUE),
        )
    )
    console.print()

    runtime = _table("runtime", "status", "version")
    for row, dist, modules in _RUNTIME:
        ok = _resolves(modules)
        status = Text("● ok", style="green") if ok else Text("○ missing", style="red")
        runtime.add_row(row, status, Text(version_of(dist) if ok else "", style="dim"))
    console.print(runtime)
    console.print()

    extras = _table("extra", "status", "install")
    for row, extra, modules in _EXTRAS:
        if _resolves(modules):
            extras.add_row(row, Text("● ok", style="green"), "")
        else:
            # Text, not a bare str: rich reads ``[demos]`` as a style tag and eats it.
            hint = Text(f'pip install "nuspace[{extra}]"', style="dim")
            extras.add_row(row, Text("○ missing", style="yellow"), hint)
    console.print(extras)
    console.print()

    points = sorted(entry_points(group=GROUP), key=lambda p: p.name)
    if points:
        installed = _table("extension", "from")
        for point in points:
            installed.add_row(point.name, Text(point.value, style="dim"))
        console.print(installed)
    else:
        console.print(Text("no extensions installed", style="dim"))
    console.print()

    on = _telemetry.telemetry_enabled()
    console.print(
        Text.assemble(
            ("telemetry: ", "dim"),
            ("on" if on else "off", "bold green" if on else "bold yellow"),
            ("  (nuspace telemetry)", "dim"),
        )
    )
