"""What an assembly holds for a run: warm imports.

:class:`Warmed` is a fabric for ``nu.Provide``, held for a worker's
span. Building a term touches nothing. A throwaway root is no resource of
its own: it is ``nustd.fs.tmp``, its ``where()`` the root the entry point
runs on. One-shot writes (the data dir made, a dir wiped) are fs writes on
the assembly's mount.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = ["Warmed"]


class Warmed(nu.Fabric):
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
