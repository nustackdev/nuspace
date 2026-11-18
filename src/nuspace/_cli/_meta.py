"""What the commands share: the console, the versions, which space, its assembly, and how it is held open.

Which space, the way ``git`` finds a repository: PATH when given, else the
nearest space at or above the current directory, else the home space (root
``~``, data in ``~/.nuspace``). ``--tmp`` is a throwaway one instead.

Which assembly runs it: the one its ``meta.json`` names, imported as
``nuspace.space.<name>``. A space without one yet, new, throwaway or made
before ``meta.json``, is :data:`DEFAULT_ASSEMBLY`'s. The commands call only
its entry points, so the command line is the same over any assembly.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import rich_click as click
from rich.console import Console
from rich.text import Text

import nu
from nuspace import _telemetry
from nuspace._branding import BLUE, header
from nuspace.errors import Refused
from nuspace.space.blocks.meta import DATA_DIR, is_space, read_meta
from nuspace.space.local.layout import made_before


if TYPE_CHECKING:
    from types import ModuleType


__all__ = [
    "DEFAULT_ASSEMBLY",
    "announce",
    "assembly",
    "console",
    "hold",
    "nearest_space",
    "path_argument",
    "space_root",
    "tilde",
    "tmp_option",
    "version_of",
]


console = Console()

#: The assembly of a space whose ``meta.json`` names none yet.
DEFAULT_ASSEMBLY = "local"

#: What a module needs to be an assembly the commands can call.
_ENTRY_POINTS = ("run", "kernel", "web", "open", "init")

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
    directory (:func:`nearest_space`), else home.
    """
    if tmp:
        if path is not None:
            raise click.UsageError("Give PATH or --tmp, not both.")
        return None
    if path is not None:
        return str(Path(path).expanduser().resolve())
    return str(nearest_space(Path.cwd()) or Path.home())


def nearest_space(start: str | Path) -> Path | None:
    """The nearest space at or above ``start``, one made before ``meta.json`` too. None when there is none."""
    here = Path(start).expanduser().resolve()
    return next((d for d in (here, *here.parents) if is_space(d) or made_before(d)), None)


def assembly(root: str | None) -> ModuleType:
    """The assembly of the space at ``root``: the one its ``meta.json`` names, else the default.

    None, a throwaway root, is the default's. A name that does not import
    as ``nuspace.space.<name>``, or imports as something without the entry
    points, is a short error, as is a ``meta.json`` that does not read.
    """
    name = DEFAULT_ASSEMBLY
    if root is not None:
        try:
            meta = read_meta(root)
        except Refused as e:
            raise click.ClickException(str(e)) from None
        if meta is not None:
            name = meta.assembly
    module = None
    if name.isidentifier():
        try:
            module = importlib.import_module(f"nuspace.space.{name}")
        except ImportError as e:
            msg = f"This space's assembly {name!r} does not import: {e}."
            raise click.ClickException(msg) from None
    if module is None or not all(hasattr(module, n) for n in _ENTRY_POINTS):
        msg = f"This space's meta.json names {name!r}, which is no assembly of nuspace.space."
        raise click.ClickException(msg)
    return module


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


def hold(term: nu.Nu) -> object:
    """Run a space until interrupted (Ctrl+C), then let the brackets close it. What the term yields.

    Closing ends what is live, interrupted, then stops the workers, the
    stores, the notification server and the lock, in that order. A run
    refused (a kernel of the space runs elsewhere, an older store format)
    is a short error. What is still queued for telemetry (see
    :mod:`nuspace._telemetry`) gets a short grace to go at the end.

    Compiled and evaluated without law validation: the space program is ours
    and tested, and validating its whole tree costs seconds per start.
    """
    try:
        value, _ = nu.eval_in_loop(nu.compile(term), nu.Context())
    except KeyboardInterrupt:
        console.print("[dim]Stopped[/dim]")
        return None
    except Refused as e:
        raise click.ClickException(str(e)) from None
    finally:
        _telemetry.flush()
    return value
