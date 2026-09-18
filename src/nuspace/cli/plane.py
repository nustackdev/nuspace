"""What a person does to one Plane from a shell: make it, change it, drop it.

A Plane is arrangement, so everything here is about how the Plane meets the
world. What is on it is :mod:`nuspace.cli.cell`.
"""

from __future__ import annotations

import rich_click as click

from nuspace import ops
from nuspace.cli.utils import console, read, require_plane, write
from nuspace.shapes import (
    DEFAULT_EDITABLE,
    DEFAULT_EXEC_MODE,
    DEFAULT_TRIGGER,
    DEFAULT_UI,
    EXEC_MODES,
    TRIGGERS,
)


__all__ = ["plane"]


def _drawn(ui: bool, editable: bool) -> str:
    """What a Plane's presentation props read as on one line."""
    if not ui:
        return "headless"
    return "ui editable" if editable else "ui"


@click.group(help="Planes: make one, change how it runs, drop it.")
def plane() -> None:
    """The ``plane`` group. Commands attach below."""


@plane.command("add", help="Write a Plane, complete, in one commit.")
@click.option("--id", "plane_id", default=None, help="The Plane's key. Minted when absent.")
@click.option("--name", default=None, help="What to call it. The id when absent.")
@click.option(
    "--exec-mode",
    type=click.Choice(EXEC_MODES),
    default=DEFAULT_EXEC_MODE,
    show_default=True,
    help="async puts the whole Plane in one process, mp gives each Cell one of its own.",
)
@click.option(
    "--trigger",
    type=click.Choice(TRIGGERS),
    default=DEFAULT_TRIGGER,
    show_default=True,
    help="When the Plane is up.",
)
@click.option(
    "--ui/--no-ui",
    default=DEFAULT_UI,
    show_default=True,
    help="Whether the Plane draws, which is what puts it in the sidebar.",
)
@click.option(
    "--editable/--no-editable",
    default=DEFAULT_EDITABLE,
    show_default=True,
    help="Whether a person can author its Cells from the Viewer.",
)
@click.pass_obj
def add(
    path: str,
    plane_id: str | None,
    name: str | None,
    exec_mode: str,
    trigger: str,
    ui: bool,
    editable: bool,
) -> None:
    """Make a Plane and say its id, which is what every other command takes."""
    plane_id = plane_id or ops.mint_ordered_id("p")
    write(
        ops.add_plane(
            plane_id=plane_id,
            name=name,
            exec_mode=exec_mode,
            trigger=trigger,
            ui=ui,
            editable=editable,
        ),
        path,
    )
    console.print(
        f"[bold]{plane_id}[/bold]  [dim]{exec_mode} {trigger} {_drawn(ui, editable)}[/dim]"
    )


@plane.command("rm", help="Drop a Plane and every Cell on it.")
@click.argument("plane_id", metavar="PLANE")
@click.pass_obj
def rm(path: str, plane_id: str) -> None:
    """Remove a Plane. Its Cells live under it and go with it."""
    require_plane(plane_id, path, read(ops.plane_exists(plane_id), path))
    write(ops.remove_plane(plane_id), path)
    console.print(f"dropped [bold]{plane_id}[/bold]", highlight=False)


@plane.command("set", help="Change a Plane's name, or how it runs, or how it is drawn.")
@click.argument("plane_id", metavar="PLANE")
@click.option("--name", default=None, help="Replace the name. Nothing restarts.")
@click.option(
    "--exec-mode", type=click.Choice(EXEC_MODES), default=None, help="Where its Cells run."
)
@click.option("--trigger", type=click.Choice(TRIGGERS), default=None, help="When the Plane is up.")
@click.option("--ui/--no-ui", default=None, help="Whether the Plane draws.")
@click.option("--editable/--no-editable", default=None, help="Whether its Cells can be authored.")
@click.pass_obj
def set_(
    path: str,
    plane_id: str,
    name: str | None,
    exec_mode: str | None,
    trigger: str | None,
    ui: bool | None,
    editable: bool | None,
) -> None:
    """Only what was named is written. A running Plane rearranges under it."""
    require_plane(plane_id, path, read(ops.plane_exists(plane_id), path))
    if name is not None:
        write(ops.rename_plane(plane_id, name), path)
    write(
        ops.set_plane_props(
            plane_id, exec_mode=exec_mode, trigger=trigger, ui=ui, editable=editable
        ),
        path,
    )
    props = read(ops.plane_props(plane_id), path)
    console.print(
        f"[bold]{plane_id}[/bold]  "
        f"[dim]{props['exec_mode']} {props['trigger']} "
        f"{_drawn(props['ui'], props['editable'])}[/dim]"
    )
