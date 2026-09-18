"""What a person does to Cells from a shell: write one, edit it, read it, drop it.

A Cell is the only thing in a Space that executes, so this is where a program
reaches the store. ``--file -`` reads the program from stdin, which is how a
Cell gets written by whatever wrote the program.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click
from rich.syntax import Syntax

from nuspace import ops
from nuspace.cli.utils import console, read, require_cell, require_plane, write
from nuspace.shapes import DEFAULT_RESTART, RESTARTS


if TYPE_CHECKING:
    from typing import IO


__all__ = ["cell"]


@click.group(help="Cells: write a program onto a Plane, edit it, read it, drop it.")
def cell() -> None:
    """The ``cell`` group. Commands attach below."""


def _row(path: str, plane_id: str, cell_id: str) -> dict:
    """One Cell's row, read off the Plane's listing so every field is total."""
    rows = read(ops.cell_rows(plane_id), path)
    return next(row for row in rows if row["id"] == cell_id)


def _props_line(cell_id: str, restart: str, reload: bool) -> str:
    """A Cell as one line: what it is called and what it does when it ends or changes."""
    said = "reload" if reload else "no reload"
    return f"[bold]{cell_id}[/bold]  [dim]restart {restart}, {said}[/dim]"


@cell.command("add", help="Write a Cell onto a Plane, program and props, in one commit.")
@click.argument("plane_id", metavar="PLANE")
@click.option("--id", "cell_id", default=None, help="The Cell's key. Minted when absent.")
@click.option("--name", default=None, help="What to call it. The id when absent.")
@click.option(
    "--template",
    type=click.Choice(ops.templates.names()),
    default=ops.DEFAULT_TEMPLATE,
    show_default=True,
    help="What the Cell starts as when no file is given.",
)
@click.option(
    "--file",
    "source_file",
    type=click.File("r"),
    default=None,
    help="The program to store. - reads stdin.",
)
@click.option(
    "--restart",
    type=click.Choice(RESTARTS),
    default=DEFAULT_RESTART,
    show_default=True,
    help="What happens when the program ends.",
)
@click.option(
    "--reload/--no-reload",
    "reload",
    default=True,
    show_default=True,
    help="Whether editing the program restarts the Cell.",
)
@click.option(
    "--index", type=int, default=None, help="Where in the Plane's order. Appended by default."
)
@click.pass_obj
def add(
    path: str,
    plane_id: str,
    cell_id: str | None,
    name: str | None,
    template: str,
    source_file: IO[str] | None,
    restart: str,
    reload: bool,
    index: int | None,
) -> None:
    """Make a Cell and say its id, which is what every other command takes."""
    require_plane(plane_id, path, read(ops.plane_exists(plane_id), path))
    cell_id = cell_id or ops.mint_ordered_id("c")
    write(
        ops.add_cell(
            plane_id,
            source_file.read() if source_file is not None else None,
            cell_id=cell_id,
            name=name,
            template=template,
            restart=restart,
            reload=reload,
            index=index,
        ),
        path,
    )
    console.print(_props_line(cell_id, restart, reload))


@cell.command("rm", help="Drop a Cell from a Plane.")
@click.argument("plane_id", metavar="PLANE")
@click.argument("cell_id", metavar="CELL")
@click.pass_obj
def rm(path: str, plane_id: str, cell_id: str) -> None:
    """Remove a Cell. A running Space cancels whatever it was running."""
    require_cell(plane_id, cell_id, path, read(ops.cell_exists(plane_id, cell_id), path))
    write(ops.remove_cell(plane_id, cell_id), path)
    console.print(f"dropped [bold]{plane_id}/{cell_id}[/bold]", highlight=False)


@cell.command("set", help="Replace a Cell's program, its name, or its lifecycle props.")
@click.argument("plane_id", metavar="PLANE")
@click.argument("cell_id", metavar="CELL")
@click.option("--name", default=None, help="Replace the name. Nothing restarts.")
@click.option(
    "--file",
    "source_file",
    type=click.File("r"),
    default=None,
    help="The program to store. - reads stdin. A Cell that reloads restarts on it.",
)
@click.option(
    "--restart", type=click.Choice(RESTARTS), default=None, help="What happens when it ends."
)
@click.option(
    "--reload/--no-reload", "reload", default=None, help="Whether editing restarts the Cell."
)
@click.pass_obj
def set_(
    path: str,
    plane_id: str,
    cell_id: str,
    name: str | None,
    source_file: IO[str] | None,
    restart: str | None,
    reload: bool | None,
) -> None:
    """Only what was named is written. The program goes last, so it restarts under the new props."""
    require_cell(plane_id, cell_id, path, read(ops.cell_exists(plane_id, cell_id), path))
    if name is not None:
        write(ops.rename_cell(plane_id, cell_id, name), path)
    write(ops.set_cell_props(plane_id, cell_id, restart=restart, reload=reload), path)
    if source_file is not None:
        write(ops.clear_error(plane_id, cell_id), path)
        write(ops.set_prog(plane_id, cell_id, source_file.read()), path)
    row = _row(path, plane_id, cell_id)
    console.print(_props_line(cell_id, row["restart"], row["reload"]))


@cell.command("show", help="A Cell's props, what it kept, and the program it holds.")
@click.argument("plane_id", metavar="PLANE")
@click.argument("cell_id", metavar="CELL")
@click.pass_obj
def show(path: str, plane_id: str, cell_id: str) -> None:
    """Everything the store knows about one Cell, the program last."""
    require_cell(plane_id, cell_id, path, read(ops.cell_exists(plane_id, cell_id), path))
    row = _row(path, plane_id, cell_id)
    console.print(_props_line(cell_id, row["restart"], row["reload"]))
    error = read(ops.error_of(plane_id, cell_id), path)
    if error:
        console.print(f"[red]failed:[/red] {error}", highlight=False)
    state = read(ops.cell_state(plane_id, cell_id), path)
    if state:
        console.print(f"[dim]state[/dim] {state}", highlight=False)
    console.print(Syntax(row["prog"], "python", word_wrap=True))
