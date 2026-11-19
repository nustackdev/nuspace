"""What an assembly holds for a run: the throwaway root, warm imports.

:class:`Throwaway` is a bracket (``nu.Bracket``): it makes the root when it
opens and removes it when it closes. The root is a real path, known when
the term is built, since the stores' SQLite files are opened by path:
``nustd.fs.tmp`` would name it only once it runs. :class:`Warmed` is a
plain class for ``nu.Provide``, held for a worker's span. Building a term
touches nothing. One-shot writes (the data dir made, a dir wiped) are no
resources: they are fs writes on the assembly's mount.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from collections.abc import Iterator

    from nu.lang.runtime import Context


__all__ = ["Throwaway", "Warmed", "throwaway"]


class Throwaway(nu.Bracket):
    """A space's root that goes when the bracket closes.

    Outermost, so the stores, the server and the lock are closed by the
    time the directory is removed.

    Args:
        path: The directory, absolute, made when the bracket opens (a term
            run twice finds it gone), removed with all it holds when it
            closes, raised or not.
        body: What runs on it. Yields what it yields.
    """

    def __init__(self, path: str | nu.Nu, *, body: nu.Nu | None = None) -> None:
        # Children: [body, path].
        super().__init__(body, path)

    @contextmanager
    def _open(self, ctx: Context, path: str) -> Iterator[None]:  # pyright: ignore[reportIncompatibleMethodOverride] - config named
        Path(path).mkdir(parents=True, exist_ok=True)
        try:
            yield
        finally:
            shutil.rmtree(path, ignore_errors=True)


def throwaway(root: str, body: nu.Nu) -> Throwaway:
    """``body`` run on the throwaway ``root``: made before, removed with all it holds after.

    The body is what makes it a space, its init first. Outermost, so
    whatever the body opens is closed by the time the root goes.

    Args:
        root: The directory, absolute, eg from ``resolve_root(None)``.
        body: What runs on it. The term yields what it yields.
    """
    return Throwaway(root, body=body)


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
