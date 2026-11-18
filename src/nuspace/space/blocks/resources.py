"""The resources an assembly binds around the stores: the throwaway root, the data dir, warm imports.

Each is a plain class for ``nu.Provide``: its setup runs when the bracket
opens, its cleanup when it closes, and none binds anything a program reads.
They are how an open touches the file system, so building an open's term
touches nothing.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from .meta import data_dir


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.lang.runtime import Context


__all__ = ["DataDir", "Throwaway", "Warmed"]


class Throwaway:
    """A space's root that goes when its bracket closes.

    Outermost, so the stores, the server and the lock are closed by the
    time the directory is removed.

    Args:
        path: The directory, made at setup (a term run twice finds it gone).
    """

    def __init__(self, path: str) -> None:
        self.path = path

    def setup(self, ctx: Context) -> None:
        """Make the directory."""
        Path(self.path).mkdir(parents=True, exist_ok=True)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: making a directory is sync work."""
        self.setup(ctx)

    def cleanup(self) -> None:
        """Remove the directory and everything the open left in it."""
        shutil.rmtree(self.path, ignore_errors=True)


class DataDir:
    """The space's data dir, made with the dirs the assembly keeps in it.

    Args:
        root: The space's root, absolute.
        dirs: The dirs to make, relative to the data dir.
    """

    def __init__(self, root: str, dirs: Sequence[str]) -> None:
        self.root = root
        self.dirs = tuple(dirs)

    def setup(self, ctx: Context) -> None:
        """Make the data dir and each of its dirs, where missing."""
        data = data_dir(self.root)
        data.mkdir(parents=True, exist_ok=True)
        for d in self.dirs:
            (data / d).mkdir(parents=True, exist_ok=True)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: making directories is sync work."""
        self.setup(ctx)


class Warmed:
    """The imports a cell run needs, paid while nobody waits on the worker.

    A spare sits idle until a body arrives, so whatever it imports then is on
    somebody's critical path. Importing here fills the module cache first,
    which is what makes a spare worth keeping.
    """

    def setup(self, ctx: Context) -> None:
        """Import what unpickling and running a body reaches for.

        A drawing run's body holds the session env's wrap and rewrite, so
        the web device's worker safe modules come too, with ``nustd.ui``.
        Never the web device's server.
        """
        import nu.prog  # noqa: F401 -- imported for the module cache
        import nustd.ui  # noqa: F401

    async def asetup(self, ctx: Context) -> None:
        """Async shim: importing is sync work."""
        self.setup(ctx)
