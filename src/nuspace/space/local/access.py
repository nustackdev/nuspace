"""local.open: a space's stores without a driver, around a body of ops.

What a script or an agent uses to read and change a space, running or
not. It needs no infra, no kernel and no device, only a space initialized
(``local.init``). It binds every store, Space, State, Web and Conn, so web
ops such as desk edits work through it.

``open`` makes nothing, resets nothing, seeds nothing and takes no lock.
With a kernel up it joins the kernel's notification server, so a write
lands in the stores and the kernel and web hear it. With none up nobody
listens: it binds the same files publishing nothing, and starts no
server. A plane run asked for through it is started by the live kernel,
or left pending for the next kernel to start.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.errors import Missing

from ..blocks.meta import data_dir, is_space, resolve_root
from ..blocks.notifier import Heard
from . import binding
from .disk import Initialized
from .layout import is_older, made_before
from .opening import ROOTS


if TYPE_CHECKING:
    import os

    from nu.context.fabric import Provide
    from nu.lang.runtime import Context


__all__ = ["open"]


class Found:
    """The space at ``root`` checked at setup: there is one. The init check comes after it.

    A space of any kind counts: one with ``meta.json``, one made before it,
    one of an older store format. :class:`~.disk.Initialized` refuses the
    ones open does not take.

    Args:
        root: The space's root, absolute.

    Raises:
        Missing: No space there at all.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def setup(self, ctx: Context) -> None:
        """Look for a space at ``root``."""
        if not (is_space(self.root) or made_before(self.root) or is_older(self.root)):
            msg = f"no space at {self.root}: make one with local.init"
            raise Missing(msg)

    async def asetup(self, ctx: Context) -> None:
        """Async shim: one small file read."""
        self.setup(ctx)


def open(
    path: str | os.PathLike[str],
    *,
    body: nu.Nu,
    blobs: Provide | None = None,
) -> nu.With:
    """The space at ``path``'s stores bound around ``body``, a body of ops. No driver runs.

    Ops run as in a cell: brackets, ``nuspace.atomic``, named targets, no
    ``Here``. Takes no lock: beside a live kernel and web, or with nothing
    up. Publishes to the kernel's notification server when it answers as
    this opens, else publishes nothing (nobody listens).

    Args:
        path: The space's root. It must be a local space, initialized.
        body: What runs with the stores bound. The term yields what it yields.
        blobs: The blob store, as ``local.kernel``. None is local's files.

    Raises:
        Missing: No space at ``path`` (at run).
        Refused: A space not initialized, another assembly's, or of an
            older store format (at run).
    """
    root, _ = resolve_root(path)
    data = str(data_dir(root))
    blobs = binding.blobs(data) if blobs is None else blobs
    stores = Heard(
        binding.valkey_dir(data),
        served=binding.stores(data, ROOTS),
        unserved=binding.quiet(data, ROOTS),
    )
    checked = [nu.Provide(Found, {"root": root}), nu.Provide(Initialized, {"root": root})]
    return nu.With(*checked, stores, blobs, body=body)
