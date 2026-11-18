"""The resources an assembly holds for a run: the throwaway root, warm imports.

Each is a plain class for ``nu.Provide``, holding something for the span
of its bracket: its setup runs when the bracket opens, its cleanup when it
closes. Building a term touches nothing. One-shot writes (the data dir
made, a dir wiped) are no resources: they are disk Commands (:mod:`.disk`).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = ["Throwaway", "Warmed", "throwaway"]


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


def throwaway(root: str, body: nu.Nu) -> nu.With:
    """``body`` run on the throwaway ``root``: made before, removed with all it holds after.

    The body is what makes it a space, its init first. Outermost, so
    whatever the body opens is closed by the time the root goes.

    Args:
        root: The directory, absolute, eg from ``resolve_root(None)``.
        body: What runs on it. The term yields what it yields.
    """
    return nu.With(nu.Provide(Throwaway, {"path": root}), body=body)


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
