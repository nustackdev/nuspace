"""``nuspace telemetry``: show or set the anonymous usage telemetry, per user.

The choice lives in ``~/.nuspace/config.json`` and holds for every space
you open. ``NUSPACE_TELEMETRY=0`` turns it off whatever the file says.
"""

from __future__ import annotations

import rich_click as click
from rich.text import Text

from nuspace import _telemetry
from nuspace._branding import BLUE

from .._meta import console


__all__ = ["telemetry"]


def _state_line(on: bool) -> Text:
    line = Text("telemetry: ", style="dim")
    line.append("on" if on else "off", style="bold green" if on else "bold yellow")
    return line


@click.group(
    short_help="Show or set anonymous usage telemetry.",
    invoke_without_command=True,
    help=(
        "Anonymous usage telemetry, for you across every space. Status with no"
        f" command. ${_telemetry.ENV}=0 turns it off whatever is set here."
    ),
)
@click.pass_context
def telemetry(ctx: click.Context) -> None:
    """Status when no command is given."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@telemetry.command(help="Show whether telemetry is on, your anonymous id and the config file.")
def status() -> None:
    """Print the state, why when the environment decides it, the id and the path."""
    console.print(_state_line(_telemetry.telemetry_enabled()))
    if _telemetry.env_override():
        console.print(f"[dim]off by ${_telemetry.ENV}, whatever the config says[/dim]")
    if _telemetry.is_dev_install():
        console.print("[dim]dev install: nothing is sent either way[/dim]")
    console.print(Text.assemble(("distinct_id: ", "dim"), (_telemetry.distinct_id(), BLUE)))
    console.print(Text.assemble(("config:      ", "dim"), (str(_telemetry.config_path()), BLUE)))


@telemetry.command(help="Turn telemetry on.")
def on() -> None:
    """Set the flag on."""
    _telemetry.set_telemetry(True)
    console.print(_state_line(True))
    if _telemetry.env_override():
        console.print(f"[dim]still off while ${_telemetry.ENV} says so[/dim]")


@telemetry.command(help="Turn telemetry off.")
def off() -> None:
    """Set the flag off."""
    _telemetry.set_telemetry(False)
    console.print(_state_line(False))
