"""What local checks on disk before a space opens: no older store format, ``meta.json`` in place.

A space made before ``meta.json`` (its Space store, no meta) is local's:
it gets its ``meta.json`` here, at the first open that makes or runs it.
This is the one bridge from before. A space of the older store format
(``kernel.sqlite``) is refused: there is no converter. A ``host.lock``
left by a single-process open of before is ignored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.errors import Refused

from ..blocks.meta import stamp
from .layout import ASSEMBLY, is_older


if TYPE_CHECKING:
    from nu.lang.runtime import Context


__all__ = ["Marked"]


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
