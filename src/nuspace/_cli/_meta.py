"""What the commands share: the console, the versions, which space, its assembly, and how it is held open.

Which space, the way ``git`` finds a repository: PATH when given, else the
nearest space at or above the current directory, else the home space (root
``~``, data in ``~/.nuspace``). ``--tmp`` is a throwaway one instead.

Which assembly runs it: the one its ``meta.json`` names, imported as
``nuspace.space.<name>``. A space without one yet, new, throwaway or made
before ``meta.json``, is :data:`DEFAULT_ASSEMBLY`'s. The command line reads
``meta.json`` the way the assemblies do, one small term over a read only
mount of its own (:func:`space_meta`). The commands call only the
assembly's entry points, so the command line is the same over any assembly.

Finding a space is plain Python, the command line being a host program:
argv to a root, the nearest one up from here looked for file by file.

How it is held: one term, one run (:func:`hold`). What the CLI needs back,
the kernel's exit status, an entry point writes into a ref the CLI hands
it (:data:`EXIT`), bound to a dict the CLI reads once the run is over.
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
import nustd.fs
from nuspace import _telemetry
from nuspace._branding import BLUE, header
from nuspace.errors import Refused
from nuspace.space.blocks.meta import DATA_DIR, META_FILE, meta_in
from nuspace.space.local.layout import MADE_BEFORE


if TYPE_CHECKING:
    from types import ModuleType

    from nuspace.space.blocks.meta import Meta


__all__ = [
    "DEFAULT_ASSEMBLY",
    "EXIT",
    "Out",
    "announce",
    "assembly",
    "console",
    "hold",
    "initialized",
    "nearest_space",
    "path_argument",
    "space_meta",
    "space_root",
    "tilde",
    "tmp_option",
    "version_of",
]


console = Console()

#: The assembly of a space whose ``meta.json`` names none yet.
DEFAULT_ASSEMBLY = "local"

#: What a module needs to be an assembly the commands can call.
_ENTRY_POINTS = ("run", "infra", "kernel", "web", "open", "init")

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
    """``--tmp``: a throwaway space instead of one found, for the commands that run one."""
    return click.option(
        "--tmp",
        is_flag=True,
        help="A throwaway space in a temp dir, initialized, gone at close. Not with one component alone.",
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


def _is_space(root: Path) -> bool:
    """Whether ``root`` holds a space: ``meta.json`` in its data dir, or a store made before it."""
    data = root / DATA_DIR
    return (data / META_FILE).is_file() or (data / MADE_BEFORE).is_file()


def nearest_space(start: str | Path) -> Path | None:
    """The nearest space at or above ``start``, one made before ``meta.json`` too. None when there is none."""
    here = Path(start).expanduser().resolve()
    return next((d for d in (here, *here.parents) if _is_space(d)), None)


#: The tag the command line mounts a space's root under, read only, to read its ``meta.json``.
MOUNT = nustd.fs.FsRef("nuspace.cli")


def space_meta(root: str) -> Meta | None:
    """``meta.json`` of the space at ``root``, or None when there is none: a small term run here.

    The root mounted read only, nothing made, the meta read as every
    assembly reads it. A root not there yet is no space.

    Raises:
        click.ClickException: The file is there but does not read as a meta.
    """
    read = meta_in(MOUNT / f"{DATA_DIR}/{META_FILE}")
    term = nustd.fs.mount(root, tag=MOUNT, readonly=True, create=False, follow="any", body=read)
    try:
        return nu.run(term)[0]
    except (FileNotFoundError, NotADirectoryError):
        return None
    except Refused as e:
        raise click.ClickException(str(e)) from None


def assembly(root: str | None) -> ModuleType:
    """The assembly of the space at ``root``: the one its ``meta.json`` names, else the default.

    None, a throwaway root, is the default's. A name that does not import
    as ``nuspace.space.<name>``, or imports as something without the entry
    points, is a short error, as is a ``meta.json`` that does not read.
    """
    name = DEFAULT_ASSEMBLY
    if root is not None:
        meta = space_meta(root)
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


def announce(path: str | None, *, alone: str | None = None, plane: str | None = None) -> None:
    """Say which space this is, and how to stop it when no server line will.

    Served, the web server prints the URL and how to stop once it is up, so
    the header leaves both to it. ``alone`` says what runs without web,
    eg ``headless``. ``path`` None is a throwaway space.
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
    if alone is not None:
        console.print(f"[dim]{alone}, Ctrl+C to stop[/dim]")


def initialized(root: str) -> bool:
    """Whether the space at ``root`` says its assembly's init ran: ``"init": true`` in its meta.json."""
    meta = space_meta(root)
    return meta is not None and meta.init


class Out(nu.Shape):
    """What a held run hands back to the CLI, in a dict the CLI binds and reads after.

    Attributes:
        code: The kernel's exit status, from an entry point that records it
            (``run(..., into=EXIT)``). 0 when nothing wrote it.
    """

    code = nu.IntRef.slot()


#: The ref an entry point writes the kernel's exit status into.
EXIT = Out.code


def hold(term: nu.Nu) -> int:
    """Run a space until interrupted (Ctrl+C), then let the brackets close it. The exit status.

    Closing ends what is live, interrupted, then stops the workers, the
    stores, the notification server and the lock, in that order. A run
    refused (a kernel of the space runs elsewhere, an older store format)
    is a short error. What is still queued for telemetry (see
    :mod:`nuspace._telemetry`) gets a short grace to go at the end.

    The term runs with :class:`Out` bound, so whatever it writes to
    :data:`EXIT` is read back: 0 when nothing did, or at a Ctrl+C here.

    Compiled and evaluated without law validation: the space program is ours
    and tested, and validating its whole tree costs seconds per start.
    """
    out: dict[str, object] = {}
    try:
        nu.eval_in_loop(nu.compile(term), nu.Context().bind(dict, out, Out))
    except KeyboardInterrupt:
        console.print("[dim]Stopped[/dim]")
        return 0
    except Refused as e:
        raise click.ClickException(str(e)) from None
    finally:
        _telemetry.flush()
    return int(out.get("code", 0))
