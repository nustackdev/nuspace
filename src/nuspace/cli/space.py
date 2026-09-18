"""What a person does to a Space from a shell: run it, look at it, empty it.

``run`` is the headless runtime: the store's write lock, the Navigator and the
change feed on sockets, the worker pool, and one arm per Plane. It holds the
Space for as long as it is up, so the other commands here are for before and
after.
"""

from __future__ import annotations

import rich_click as click
from rich.text import Text

import nu
from nu._config.branding import BLUE, PURPLE
from nuspace import ops
from nuspace.cli.utils import console, read, write
from nuspace.exec import run_space
from nuspace.shapes import TRIGGER_BOOT, TRIGGERS
from nuspace.space import DEFAULT_NAME, open_space


__all__ = ["clear", "ls", "run"]


def _plane_line(row: dict) -> Text:
    """One Plane: its id, the name where it differs, and its three props."""
    line = Text.assemble((str(row["id"]), f"bold {BLUE}"))
    if row["name"] != row["id"]:
        line.append(f"  {row['name']}")
    line.append(f"  {row['exec_mode']} {row['trigger']} {row['viewer']}", style="dim")
    return line


def _cell_line(row: dict, status: dict) -> Text:
    """One Cell: its id, what it does when it ends or changes, and how it is."""
    line = Text.assemble(("  ", ""), (str(row["id"]), "bold"))
    if row["name"] != row["id"]:
        line.append(f"  {row['name']}")
    reload_ = "reload" if row["reload"] else "no reload"
    line.append(f"  restart {row['restart']}, {reload_}", style="dim")
    if status.get("error"):
        line.append(f"  failed: {status['error']}", style="red")
    return line


@click.command(help="List the Planes in the Space and the Cells on each.")
@click.pass_obj
def ls(path: str) -> None:
    """The whole tree, two reads: the Planes, then every Plane's Cells."""
    planes = read(ops.plane_rows(), path)
    if not planes:
        console.print(f"[dim]{path}: no Planes yet[/dim]")
        return
    contents = read(
        nu.List.of(
            *[
                nu.Dict.of(cells=ops.cell_rows(row["id"]), status=ops.cell_statuses(row["id"]))
                for row in planes
            ]
        ),
        path,
    )
    console.print(Text(path, style="dim"))
    for row, held in zip(planes, contents, strict=True):
        console.print(_plane_line(row))
        statuses = {s["id"]: s for s in held["status"]}
        for cell in held["cells"]:
            console.print(_cell_line(cell, statuses.get(cell["id"], {})))


@click.command(help="Open the Space and run it headless until interrupted.")
@click.option(
    "-t",
    "--trigger",
    "triggers",
    multiple=True,
    type=click.Choice(TRIGGERS),
    default=(TRIGGER_BOOT,),
    show_default=True,
    help="Which Planes this runtime brings up. Repeat for more than one.",
)
@click.option(
    "--address", default=None, help="host:port for the Navigator. A free port by default."
)
@click.option(
    "--feed-address", default=None, help="host:port for the change feed. A free port by default."
)
@click.option("--name", default=DEFAULT_NAME, show_default=True, help="Worker process name prefix.")
@click.pass_obj
def run(
    path: str,
    triggers: tuple[str, ...],
    address: str | None,
    feed_address: str | None,
    name: str,
) -> None:
    """Run until Ctrl+C, then let the brackets reap the fleet on the way out.

    ``max_parallel=1`` because nothing in the runtime computes: every branch is
    an await, and a larger budget rations each Plane's arm against a semaphore
    those arms never give back.
    """
    wanted = [row for row in read(ops.plane_rows(), path) if row["trigger"] in triggers]
    console.print(Text.assemble(("nuspace", f"bold {PURPLE}"), ("  ", ""), (path, "dim")))
    if wanted:
        for row in wanted:
            console.print(_plane_line(row))
    else:
        console.print(f"[dim]nothing to bring up for trigger {', '.join(triggers)}[/dim]")
    console.print("[dim]running, Ctrl+C to stop[/dim]")
    try:
        nu.run_in_loop(
            open_space(
                run_space(triggers=tuple(triggers)),
                path=path,
                address=address,
                feed_address=feed_address,
                name=name,
            ),
            nu.Context(),
            max_parallel=1,
        )
    except KeyboardInterrupt:
        console.print("[dim]stopped[/dim]")


@click.command(help="Drop every Plane, leaving the Space open and empty.")
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation.")
@click.pass_obj
def clear(path: str, yes: bool) -> None:
    """Empty the Space. The store directory itself stays where it is."""
    planes = read(ops.plane_ids(), path)
    if not planes:
        console.print(f"[dim]{path}: already empty[/dim]")
        return
    if not yes:
        click.confirm(f"drop {len(planes)} Plane(s) from {path}?", abort=True)
    write(ops.clear_space(), path)
    console.print(f"cleared {len(planes)} Plane(s) from [dim]{path}[/dim]", highlight=False)
