"""local.open and local.init: a space's stores without a driver.

- :func:`open`: the stores bound beside whatever runs, a body of ops, no
  driver, no lock. What a script or an agent uses to read and change a
  space, running or not.
- :func:`init`: the space made and seeded as its first kernel and web
  would, nothing run. Refused while either driver runs.

``open`` makes nothing, resets nothing and seeds nothing. It joins the
notifier a live kernel or web owns, or owns one for its own life, so a
write lands in the stores and a live kernel hears it. A plane run asked
for through it is started by the live kernel, or left pending for the
next kernel to start.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import system
from nuspace.errors import Missing, Refused
from nuspace.web.planes import ensure as web_planes

from ..blocks.meta import data_dir, read_meta, resolve_root
from . import binding
from ._common import bound, opening, path_set
from .layout import ASSEMBLY, KERNEL_LOCK, WEB_LOCK


if TYPE_CHECKING:
    import os

    from nu.context.fabric import Provide
    from nu.lang.runtime import Context


__all__ = ["init", "open"]


class Found:
    """The space at ``root`` checked at setup: it has ``meta.json``, and local made it.

    Args:
        root: The space's root, absolute.

    Raises:
        Missing: No space there (no ``meta.json``).
        Refused: Another assembly made it.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    def setup(self, ctx: Context) -> None:
        """Read ``meta.json`` and check the assembly it names."""
        meta = read_meta(self.root)
        if meta is None:
            msg = f"no space at {self.root}: make one with local.init, or run it first"
            raise Missing(msg)
        if meta.assembly != ASSEMBLY:
            msg = (
                f"{self.root} is a space of the {meta.assembly!r} assembly, not {ASSEMBLY!r}."
                f" Open it with {meta.assembly!r}"
            )
            raise Refused(msg)

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
    up. Joins the notifier that answers, or owns one until ``body`` ends.

    Args:
        path: The space's root. It must be a local space already.
        body: What runs with the stores bound. The term yields what it yields.
        blobs: The blob store, as ``local.kernel``. None is local's files.

    Raises:
        Missing: No space at ``path`` (at run).
        Refused: Another assembly's space (at run).
    """
    root, _ = resolve_root(path)
    data = str(data_dir(root))
    blobs = binding.blobs(data) if blobs is None else blobs
    return nu.With(nu.Provide(Found, {"root": root}), *bound(data, blobs), body=body)


def init(path: str | os.PathLike[str]) -> nu.With:
    """The space at ``path`` made and seeded as its first kernel and web would, then closed. Nothing runs.

    The data dir, ``meta.json``, every store and its containers (the
    kernel's live indexes too), the system planes and web's planes, made
    where missing; ``Space.info.path`` written. No reap, no workers, no
    driver, so Conn is left as it is. A space already there keeps what it
    holds. Both driver locks are held while it works.

    Raises:
        Refused: An older store format, another assembly's space, or a
            kernel or a web of this space running.
    """
    root, _ = resolve_root(path)
    return opening(
        root,
        throwaway=False,
        locks=[(KERNEL_LOCK, "kernel"), (WEB_LOCK, "web")],
        log=None,
        blobs=None,
        body=path_set(root) >> system.ensure() >> web_planes(),
    )
