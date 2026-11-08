"""What the commands share: the console, the versions, which space, and how it is held open.

Which space, the way ``git`` finds a repository: PATH when given, else the
nearest space at or above the current directory, else the home space (root
``~``, data in ``~/.nuspace``). ``--tmp`` is a throwaway one instead.
"""

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
from nuspace.errors import Refused
from nuspace.host.layout import DATA_DIR, find_space


__all__ = [
    "announce",
    "console",
    "hold",
    "path_argument",
    "space_root",
    "tilde",
    "tmp_option",
    "version_of",
]


console = Console()

_F = TypeVar("_F", bound=Callable[..., Any])


def version_of(package: str) -> str:
    """The installed version of ``package``, or a dev marker when it is not installed."""
    try:
        return version(package)
    except PackageNotFoundError:
        return "0.0.0+dev"


def path_argument(fn: _F) -> _F:
    """The space's root a command takes, positional and optional: see :func:`space_root`."""
    return click.argument("path", required=False)(fn)


def tmp_option(fn: _F) -> _F:
    """``--tmp``: a throwaway space instead of one found, for the commands that open one."""
    return click.option(
        "--tmp", is_flag=True, help="A throwaway space in a temp dir, gone at close."
    )(fn)


def space_root(path: str | None, *, tmp: bool = False) -> str | None:
    """The root of the space a command means, absolute. None with ``tmp``, a throwaway.

    PATH when given, else the nearest space at or above the current
    directory, else home.
    """
    if tmp:
        if path is not None:
            raise click.UsageError("Give PATH or --tmp, not both.")
        return None
    if path is not None:
        return str(Path(path).expanduser().resolve())
    return str(find_space(Path.cwd()) or Path.home())


def tilde(path: str | Path) -> str:
    """``path`` as a person reads it: absolute, home as ``~``."""
    root = Path(path).expanduser().resolve()
    try:
        return str(Path("~") / root.relative_to(Path.home().resolve()))
    except ValueError:
        return str(root)


def announce(path: str | None, *, headless: bool = False, plane: str | None = None) -> None:
    """Say which space this is, and how to stop it when no server line will.

    Served, the web server prints the URL and how to stop once it is up, so
    the header leaves both to it.
    """
    console.print(
        header(
            "sm",
            version=version_of("nuspace"),
            where="throwaway space, gone at close"
            if path is None
            else f"Path: {tilde(Path(path) / DATA_DIR)}",
        ),
        highlight=False,
        soft_wrap=True,
    )
    if plane is not None:
        console.print(
            Text.assemble(("plane ", "dim"), (plane, BLUE)), highlight=False, soft_wrap=True
        )
    if headless:
        console.print("[dim]headless, Ctrl+C to stop[/dim]")


def hold(term: nu.Nu) -> None:
    """Run a space until interrupted (Ctrl+C), then let the brackets close it.

    Closing ends what is live, interrupted, then stops the workers, the
    stores, the notification server and the lock, in that order. An open
    the host refuses (another host holds the space, an older store format)
    is a short error. What is still queued for telemetry (see
    :mod:`nuspace._telemetry`) gets a short grace to go at the end.

    Compiled and evaluated without law validation: the space program is ours
    and tested, and validating its whole tree costs seconds per start.
    """
    try:
        nu.eval_in_loop(nu.compile(term), nu.Context())
    except KeyboardInterrupt:
        console.print("[dim]Stopped[/dim]")
    except Refused as e:
        raise click.ClickException(str(e)) from None
    finally:
        _telemetry.flush()
