"""Helpers the commands share: where the store is, and running one tree against it.

A Space is a directory RocksDB holds an exclusive lock on, so exactly one
process has it at a time. That is the whole shape of this CLI: a one shot
command opens the store, runs one tree, and closes it again, and ``run`` holds
it for as long as the Space is up. Seed a Space with the commands, then run it.

Helpers are not concepts, so they sit here rather than in a module of their
own. Nothing here composes a tree: the commands do that out of ops, and these
only carry one to the store and back.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import rich_click as click
from rich.console import Console

import nu
import nustd.kv
from nuspace.shapes import Space
from nuspace.space import store


__all__ = [
    "DEFAULT_STORE",
    "STORE_ENV",
    "console",
    "nuspace_version",
    "read",
    "require_cell",
    "require_plane",
    "write",
]


#: The Space a command works on when nobody said which.
DEFAULT_STORE = ".nuspace"

#: The environment variable that says which Space, so a shell session picks one
#: once instead of every command repeating it.
STORE_ENV = "NUSPACE_STORE"


console = Console()


def nuspace_version() -> str:
    """The installed version, or a dev marker when nuspace is not installed."""
    try:
        return version("nuspace")
    except PackageNotFoundError:
        return "0.0.0+dev"


def write(tree: nu.Nu, path: str, *, root: type[Space] = Space) -> None:
    """Run a write against the Space at ``path``, then close the store.

    Every op brackets itself already, and the pass here puts one more around
    whatever the command composed, so a command that runs two ops is still one
    thing the runtime wakes on.
    """
    nu.run_in_loop(
        nu.With(store(path, root=root), body=nustd.kv.auto_flow_atomic(tree, scope=root)),
        nu.Context(),
    )


def read(tree: nu.Nu, path: str, *, root: type[Space] = Space) -> object:
    """What a read says about the Space at ``path``, the store open only for it."""
    value, _ = nu.run_in_loop(
        nu.With(store(path, root=root), body=nustd.kv.Snapshot(tree, scope=root)),
        nu.Context(),
    )
    return value


def require_plane(plane: str, path: str, exists: object) -> None:
    """Stop with a message when the Plane is not there.

    Every write op is guarded, so addressing something absent is already
    harmless. It is also silent, and a person who mistyped an id deserves to
    hear about it rather than watch nothing happen.
    """
    if not exists:
        console.print(f"[red]no such Plane:[/red] [bold]{plane}[/bold] in {path}", highlight=False)
        raise click.exceptions.Exit(2)


def require_cell(plane: str, cell: str, path: str, exists: object) -> None:
    """Stop with a message when the Cell is not on that Plane."""
    if not exists:
        console.print(
            f"[red]no such Cell:[/red] [bold]{plane}/{cell}[/bold] in {path}", highlight=False
        )
        raise click.exceptions.Exit(2)
