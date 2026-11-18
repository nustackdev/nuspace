"""What local does on disk around an open: the space checked and marked, the uploads dir wiped.

A space made before ``meta.json`` (its Space store, no meta) is local's:
it gets its ``meta.json`` here, at the first open that makes or runs it.
This is the one bridge from before. A space of the older store format
(``kernel.sqlite``) is refused: there is no converter. A ``host.lock``
left by a single-process open of before is ignored.

The uploads dir holds files tabs posted, read by workers by path: no tab
outlives the web that served it, so local wipes the dir before web starts.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nuspace.errors import Refused

from ..blocks.meta import stamp
from .layout import ASSEMBLY, is_older


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.lang.runtime import Context


__all__ = ["Marked", "Wiped"]


class Marked:
    """The space at ``root`` checked and marked as local's, at setup. Before anything is written.

    Args:
        root: The space's root, absolute.

    Raises:
        Refused: ``root`` holds a space of an older store format, or one
            another assembly made.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def setup(self, ctx: Context) -> None:
        """Refuse an older space or another assembly's; write ``meta.json`` where missing."""
        if is_older(self.root):
            msg = (
                f"{self.root} holds a space of an older nuspace store format."
                " There is no converter: open a fresh directory."
            )
            raise Refused(msg)
        stamp(self.root, ASSEMBLY)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: a check and a small file write."""
        self.setup(ctx)


class Wiped:
    """Dirs removed with all they hold, at setup. Before anything writes in them.

    Args:
        dirs: The dirs, absolute. A missing one is fine.
    """

    def __init__(self, dirs: Sequence[str]) -> None:
        self.dirs = tuple(dirs)

    def setup(self, ctx: Context) -> None:
        """Remove each dir, where there."""
        for d in self.dirs:
            shutil.rmtree(d, ignore_errors=True)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: removing files is sync work."""
        self.setup(ctx)
