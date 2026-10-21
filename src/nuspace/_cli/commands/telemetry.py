"""``nuspace telemetry``: show or set the anonymous usage telemetry, per user.

The choice lives in ``~/.nuspace/config.json`` and holds for every space
you open. ``NUSPACE_TELEMETRY=0`` turns it off whatever the file says.
"""

from __future__ import annotations

from pathlib import Path

import rich_click as click
from rich.text import Text

from nuspace import _telemetry
from nuspace._branding import BLUE, PURPLE

from .._meta import console


__all__ = ["telemetry"]


#: Why we ask, said once wherever the choice is shown.
_WHY = (
    "nuspace is still young, and these few anonymous events help us a lot."
    " We'd appreciate it if you kept telemetry on."
)

#: What goes out and what never does, as ``(label, text)`` rows.
_WHAT = (
    ("events", "a space or its UI opened, a plane or a cell added or removed"),
    ("details", "nuspace, nu and Python versions, OS and CPU type, an anonymous id"),
    ("never", "your code, names, outputs, file paths, or anything else in your spaces"),
)


def _state_line(on: bool) -> Text:
    line = Text("telemetry: ", style="dim")
    line.append("on" if on else "off", style="bold green" if on else "bold yellow")
    return line


def _heading(title: str) -> Text:
    return Text(title, style=f"bold {PURPLE}")


def _row(label: str, value: str, style: str = "") -> Text:
    return Text.assemble((f"  {label:<10}", "dim"), (value, style))


def _switch(on: bool) -> str:
    """How to flip it from here."""
    if on:
        return "nuspace telemetry off"
    if _telemetry.env_override():
        return f"unset ${_telemetry.ENV}"
    return "nuspace telemetry on"


def _where(path: Path) -> str:
    """``path`` as a person reads it, home as ``~``."""
    try:
        return str(Path("~") / path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _print(*lines: Text | str) -> None:
    for line in lines:
        console.print(line, highlight=False, soft_wrap=True)


@click.group(
    short_help="Show or set anonymous usage telemetry.",
    invoke_without_command=True,
    help=(
        "Anonymous usage telemetry, set once for you across every space. It sends a few usage"
        " events, never anything from inside your spaces. Status with no command. nuspace is"
        " still young, so we'd appreciate you keeping it on."
        f" ${_telemetry.ENV}=0 turns it off whatever is set here."
    ),
)
@click.pass_context
def telemetry(ctx: click.Context) -> None:
    """Status when no command is given."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@telemetry.command(help="Show whether telemetry is on, what it sends, your anonymous id.")
def status() -> None:
    """Print the state and why, what is sent and what never is, the id, the path, how to switch."""
    on = _telemetry.telemetry_enabled()
    _print(_state_line(on))
    if _telemetry.env_override():
        _print(f"[dim]off by ${_telemetry.ENV}, whatever the config says[/dim]")
    if _telemetry.is_dev_install():
        _print("[dim]dev install: nothing is sent either way[/dim]")
    _print(
        "",
        _heading("What we collect"),
        *(_row(label, text) for label, text in _WHAT),
        "",
        _heading("Your settings"),
        _row("id", _telemetry.distinct_id(), BLUE),
        _row("config", _where(_telemetry.config_path()), BLUE),
        _row("turn " + ("off" if on else "on"), _switch(on), BLUE),
        "",
        f"[dim]{_WHY}[/dim]",
    )


@telemetry.command(help="Turn telemetry on.")
def on() -> None:
    """Set the flag on."""
    _telemetry.set_telemetry(True)
    _print(_state_line(True))
    if _telemetry.env_override():
        _print(f"[dim]still off while ${_telemetry.ENV} says so[/dim]")
    else:
        _print("[dim]Thank you, it helps a lot while nuspace is young.[/dim]")


@telemetry.command(help="Turn telemetry off.")
def off() -> None:
    """Set the flag off."""
    _telemetry.set_telemetry(False)
    _print(
        _state_line(False),
        "[dim]Nothing will be sent from here on. If you change your mind:"
        " nuspace telemetry on[/dim]",
    )
