"""``nuspace verse``: the packages extending this install, and the planes each adds.

One line per package registering under the ``nuspace.extensions`` entry
points: its name, its version, the short names of the planes it adds, and
how many cells and content kinds. ``nuspace run --with`` takes a plane as
``pkg.plane``, the package and the short name. A package whose extension
fails to load says why on a dim line under it.
"""

from __future__ import annotations

import json

import rich_click as click
from rich.text import Text

from nuspace._branding import BLUE, PURPLE

from .._installed import Installed, installed
from .._meta import console


__all__ = ["verse"]


def _detail(package: Installed) -> dict[str, object]:
    ext = package.extension
    return {
        "name": package.name,
        "version": package.version,
        "planes": [
            {"name": f"{package.name}.{p.name}", "label": p.label, "description": p.description}
            for p in (ext.planes if ext else ())
        ],
        "cells": [
            {"name": s.name, "label": s.label, "description": s.description}
            for s in (ext.cells if ext else ())
        ],
        "contents": [
            {"name": f"{package.name}.{c.name}", "label": c.label, "description": c.description}
            for c in (ext.contents if ext else ())
        ],
        "envs": sorted(ext.envs) if ext else [],
        "error": package.error or None,
    }


def _line(package: Installed, name_width: int, version_width: int) -> Text:
    line = Text.assemble(
        (package.name.ljust(name_width), f"bold {PURPLE}"),
        ("  ", ""),
        (package.version.ljust(version_width), "dim"),
    )
    ext = package.extension
    if ext is not None and ext.planes:
        line.append("  ")
        line.append(" · ".join(p.name for p in ext.planes), style=BLUE)
    if ext is not None and ext.cells:
        line.append(f"  +{len(ext.cells)} cells", style="dim")
    if ext is not None and ext.contents:
        line.append(f"  +{len(ext.contents)} content kinds", style="dim")
    line.rstrip()
    return line


@click.command(
    short_help="List the installed packages and the planes they add.",
    help=(
        "List every installed package extending nuspace: its version, the planes it"
        " adds and how many cells. Open one with: nuspace run --with <pkg>.<plane>"
    ),
)
@click.option(
    "--json", "as_json", is_flag=True, help="Everything, as JSON, planes named pkg.plane."
)
def verse(as_json: bool) -> None:
    """Print the packages."""
    packages = installed()
    if as_json:
        click.echo(json.dumps({"packages": [_detail(p) for p in packages]}, indent=2))
        return
    if not packages:
        console.print(Text("no packages extend nuspace here", style="dim"))
        return
    name_width = max(len(p.name) for p in packages)
    version_width = max(len(p.version) for p in packages)
    for package in packages:
        console.print(_line(package, name_width, version_width), highlight=False)
        if package.error:
            console.print(Text(f"  {package.error}", style="dim"), highlight=False)
