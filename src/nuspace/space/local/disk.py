"""What local does on disk around an entry point: the space marked, flagged, checked; the uploads dir wiped.

``init`` marks the space (:class:`Marked`), and flags it once its inits are
done (:class:`Flagged`). Every other entry point checks that flag first
(:class:`Initialized`) and refuses a space without it.

A space made before ``meta.json`` (its Space store, no meta) is local's:
``init`` gives it its ``meta.json``. This is the one bridge from before. A space of the older store format
(``kernel.sqlite``) is refused: there is no converter. A ``host.lock``
left by a single-process open of before is ignored.

The uploads dir holds files tabs posted, read by workers by path: no tab
outlives the web that served it, so local wipes the dir before web starts.
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nuspace.errors import Refused

from ..blocks.meta import read_meta, set_init, stamp
from .layout import ASSEMBLY, is_older


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.lang.runtime import Context


__all__ = ["Flagged", "Initialized", "Marked", "Wiped"]


def refuse_older(root: str) -> None:
    """Refuse ``root`` when it holds a space of an older store format."""
    if is_older(root):
        msg = (
            f"{root} holds a space of an older nuspace store format."
            " There is no converter: open a fresh directory."
        )
        raise Refused(msg)


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
        refuse_older(self.root)
        stamp(self.root, ASSEMBLY)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: a check and a small file write."""
        self.setup(ctx)


class Initialized:
    """The space at ``root`` checked at setup: local's, and its init done. Writes nothing.

    Every entry point but ``init`` holds it outermost, so a space is
    refused before anything is made or locked.

    Args:
        root: The space's root, absolute.

    Raises:
        Refused: ``root`` holds a space of an older store format, or one
            another assembly made, or its ``meta.json`` is missing or lacks
            ``"init": true`` (a space made before this flag too).
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def setup(self, ctx: Context) -> None:
        """Read ``meta.json``: refuse an older space, another assembly's, or one not initialized."""
        refuse_older(self.root)
        meta = read_meta(self.root)
        if meta is not None and meta.assembly != ASSEMBLY:
            msg = (
                f"{self.root} is a space of the {meta.assembly!r} assembly, not {ASSEMBLY!r}."
                f" Open it with {meta.assembly!r}"
            )
            raise Refused(msg)
        if meta is None or not meta.init:
            msg = f"the space at {self.root} is not initialized: run nuspace init, or local.init"
            raise Refused(msg)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: one small file read."""
        self.setup(ctx)


class Flagged:
    """The space at ``root`` flagged initialized at setup: ``"init": true`` in its ``meta.json``.

    Run as the last step of ``init``, a bracket around nothing: the flag is
    written only once every init before it is done.

    Args:
        root: The space's root, absolute, marked already.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def setup(self, ctx: Context) -> None:
        """Write the flag."""
        set_init(self.root)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: a small file write."""
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
