"""The resources an open binds around the stores: the throwaway root, the data dir, fresh files, warm imports.

Each is a plain class for ``nu.Provide``: its setup runs when the bracket
opens, its cleanup when it closes, and none binds anything a program reads.
They are how an open touches the file system, so building an open's term
touches nothing.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from nuspace.errors import Refused

from .layout import DATA_DIR, is_older


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.lang.runtime import Context


__all__ = ["DataDir", "Fresh", "Throwaway", "Warmed"]


#: What SQLite keeps beside a database file.
_SIDE = ("-wal", "-shm", "-journal")


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
    """The space's data dir, made with the folders its store files sit in. Refuses an older space.

    Args:
        root: The space's root, absolute.
        files: The store files, relative to the data dir.

    Raises:
        Refused: ``root`` holds a space of an older store format. No converter.
    """

    def __init__(self, root: str, files: Sequence[str]) -> None:
        self.root = root
        self.files = tuple(files)

    def setup(self, ctx: Context) -> None:
        """Refuse an older space, then make the data dir and its store folders."""
        if is_older(self.root):
            msg = (
                f"{self.root} holds a space of an older nuspace store format."
                " There is no converter: open a fresh directory."
            )
            raise Refused(msg)
        data = Path(self.root) / DATA_DIR
        for file in self.files:
            (data / file).parent.mkdir(parents=True, exist_ok=True)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: making directories is sync work."""
        self.setup(ctx)


class Fresh:
    """Store files deleted at setup, so their stores open empty. Before their navigators.

    Args:
        paths: The database files, absolute. What SQLite keeps beside each
            goes too.
    """

    def __init__(self, paths: Sequence[str]) -> None:
        self.paths = tuple(paths)

    def setup(self, ctx: Context) -> None:
        """Delete each file and its side files, where there."""
        for path in self.paths:
            for suffix in ("", *_SIDE):
                Path(path + suffix).unlink(missing_ok=True)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: deleting files is sync work."""
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
        import nuspace.devices.web.env
        import nuspace.kernel.body
        import nuspace.kernel.out  # noqa: F401
        import nustd.ui  # noqa: F401

    async def asetup(self, ctx: Context) -> None:
        """Async shim: importing is sync work."""
        self.setup(ctx)
