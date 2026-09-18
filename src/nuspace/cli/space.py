"""What a person does to a Space from a shell: run it, open it, look at it, empty it.

``run`` and ``serve`` are the two assembled trees: the store's write lock, the
Navigator and the change feed on sockets, the worker pool, and one arm per
Plane, with a browser server on top in the second one. Either holds the Space
for as long as it is up, so the other commands here are for before and after.
"""

from __future__ import annotations

import rich_click as click
from rich.text import Text

import nu
from nu._config.branding import BLUE, PURPLE
from nuspace import ops, presets
from nuspace.cli.utils import console, read, write
from nuspace.shapes import TRIGGER_BOOT, TRIGGER_NAV, TRIGGERS
from nuspace.space import DEFAULT_NAME


__all__ = ["clear", "ls", "run", "serve"]


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
    """Run until Ctrl+C, then let the brackets reap the fleet on the way out."""
    _announce(path, triggers)
    console.print("[dim]running, Ctrl+C to stop[/dim]")
    _hold(
        presets.headless(
            path=path,
            triggers=tuple(triggers),
            address=address,
            feed_address=feed_address,
            name=name,
        )
    )


@click.command(help="Open the Space and serve it in the browser until interrupted.")
@click.option(
    "-t",
    "--trigger",
    "triggers",
    multiple=True,
    type=click.Choice(TRIGGERS),
    default=(TRIGGER_BOOT,),
    show_default=True,
    help="Which Planes are up without a browser asking. A nav Plane never is.",
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("-p", "--port", default=8080, show_default=True, help="Port to bind.")
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab on the way up.")
@click.option(
    "--address", default=None, help="host:port for the Navigator. A free port by default."
)
@click.option(
    "--feed-address", default=None, help="host:port for the change feed. A free port by default."
)
@click.option(
    "--session-address",
    default=None,
    help="host:port for the live connections. A free port by default.",
)
@click.option("--name", default=DEFAULT_NAME, show_default=True, help="Worker process name prefix.")
@click.pass_obj
def serve(
    path: str,
    triggers: tuple[str, ...],
    host: str,
    port: int,
    no_browser: bool,
    address: str | None,
    feed_address: str | None,
    session_address: str | None,
    name: str,
) -> None:
    """Serve until Ctrl+C. A Plane is up because a tab navigated to it, or a trigger said so."""
    _announce(path, triggers)
    listed = [row for row in read(ops.plane_rows(), path) if row["trigger"] == TRIGGER_NAV]
    console.print(f"[dim]{len(listed)} Plane(s) a tab can navigate to[/dim]")
    console.print(f"[dim]http://{host}:{port}/pages, Ctrl+C to stop[/dim]")
    _hold(
        presets.full(
            path=path,
            triggers=tuple(triggers),
            host=host,
            port=port,
            open_browser=not no_browser,
            address=address,
            feed_address=feed_address,
            session_address=session_address,
            name=name,
        )
    )


def _announce(path: str, triggers: tuple[str, ...]) -> None:
    """Say which Space this is and which Planes come up without being asked."""
    wanted = [row for row in read(ops.plane_rows(), path) if row["trigger"] in triggers]
    console.print(Text.assemble(("nuspace", f"bold {PURPLE}"), ("  ", ""), (path, "dim")))
    if wanted:
        for row in wanted:
            console.print(_plane_line(row))
    else:
        console.print(f"[dim]nothing to bring up for trigger {', '.join(triggers)}[/dim]")


def _hold(tree: nu.Nu) -> None:
    """Run a preset until interrupted, then let the brackets reap the fleet.

    ``max_parallel=1`` because nothing in the runtime computes: every branch is
    an await, and a larger budget rations each Plane's arm against a semaphore
    those arms never give back.
    """
    try:
        nu.run_in_loop(tree, nu.Context(), max_parallel=1)
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
