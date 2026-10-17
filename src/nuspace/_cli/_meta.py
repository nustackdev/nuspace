"""What the commands share: the console, the versions, and how a space is held open."""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, TypeVar

import rich_click as click
from rich.console import Console
from rich.text import Text

import nu
from nuspace import _telemetry
from nuspace._branding import BLUE, header
from nuspace.system.kernel import NotASpace


__all__ = [
    "STORE_ENV",
    "announce",
    "console",
    "hold",
    "opened",
    "path_argument",
    "version_of",
]


#: The environment variable naming the space directory when no path is given.
STORE_ENV = "NUSPACE_STORE"

console = Console()

_F = TypeVar("_F", bound=Callable[..., Any])


def version_of(package: str) -> str:
    """The installed version of ``package``, or a dev marker when it is not installed."""
    try:
        return version(package)
    except PackageNotFoundError:
        return "0.0.0+dev"


def path_argument(fn: _F) -> _F:
    """The space directory a command takes, from :data:`STORE_ENV` when absent."""
    return click.argument("path", required=False, envvar=STORE_ENV)(fn)


def _where(path: str | None) -> str:
    """The space directory as a person reads it: absolute, home as ``~``."""
    if path is None:
        return "throwaway space, gone at close"
    root = Path(path).expanduser().resolve()
    try:
        return str(Path("~") / root.relative_to(Path.home()))
    except ValueError:
        return str(root)


def announce(path: str | None, *, headless: bool = False, plane: str | None = None) -> None:
    """Say which space this is, and how to stop it when no server line will.

    Served, the web server prints the URL and how to stop once it is up, so
    the header leaves both to it.
    """
    console.print(
        header("sm", version=version_of("nuspace"), where=_where(path)),
        highlight=False,
        soft_wrap=True,
    )
    if plane is not None:
        console.print(
            Text.assemble(("plane ", "dim"), (plane, BLUE)), highlight=False, soft_wrap=True
        )
    if headless:
        console.print("[dim]headless, Ctrl+C to stop[/dim]")


def opened(preset: Callable[..., nu.Nu], *args: object, **kwargs: object) -> nu.Nu:
    """What ``preset`` opens, or a short error when the path is not a space."""
    try:
        return preset(*args, **kwargs)
    except NotASpace as e:
        raise click.ClickException(str(e)) from None


def hold(term: nu.Nu) -> None:
    """Run a space until interrupted, then let the brackets reap the fleet.

    The user's first run event goes out here (see :mod:`nuspace._telemetry`):
    on opening a space, never on import. Compiled and evaluated without law
    validation: the space program is ours and tested, and validating its
    whole tree costs seconds per start.
    """
    _telemetry.first_run()
    try:
        nu.eval_in_loop(nu.compile(term), nu.Context())
    except KeyboardInterrupt:
        console.print("[dim]Stopped[/dim]")
