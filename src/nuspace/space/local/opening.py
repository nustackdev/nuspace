"""What local's entry points share: ``init``, and the brackets from the init check to every store bound.

``init`` makes the space and runs each component's init, once::

    meta.json             an older format refused, another assembly's refused,
                          written where missing (a space made before it is adopted)
    the data dir          made, with local's dirs
    locks                 infra's, the kernel's, web's: refused while any runs
    Space, State, Web, Conn   bound quiet: nothing runs, so nobody listens
    inits                 core's (the Space format checked first), the
                          kernel's, web's, each its own commits
    Space.info.path       the space's root
    "init": true          in meta.json, last: a failed init leaves it false

Every entry point that runs a driver opens the space the same way after
it, each step inside the brackets of the ones before::

    the init check        refused when meta.json lacks "init": true
    the data dir          local's dirs, made where missing
    locks                 one per driver the entry point runs, or Refused
    log                   this process's logging at the driver's file
    the notifier          the kernel's: started and owned by the kernel,
                          joined by web (refused with no kernel up)
    Space, State, Web, Conn   bound (:mod:`.binding`), publishing
    blobs                 when the entry point binds them

A throwaway root (path None) is made by the entry point itself, so it
runs ``init`` on it first, at setup (:func:`fresh`). ``open`` shares only the
bindings and the init check: it locks nothing and makes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nuspace.web
import nustd.kv
from nuspace import kernel
from nuspace.shapes import Space, stores
from nuspace.web.stores import CONN_STORE, WEB_STORE

from ..blocks.lock import Lock
from ..blocks.logs import logged_to
from ..blocks.meta import data_dir, resolve_root
from ..blocks.resources import DataDir, Throwaway
from . import binding
from .disk import Flagged, Initialized, Marked
from .layout import DIRS, INFRA_LOCK, KERNEL_LOCK, WEB_LOCK


if TYPE_CHECKING:
    import os
    from collections.abc import Sequence

    from nu.context.fabric import Provide
    from nu.lang.runtime import Context


__all__ = ["ROOTS", "STORES", "Prepared", "bracketed", "fresh", "init", "path_set"]


#: Every store local binds: the core ones, then web's.
STORES = (*stores.CORE, WEB_STORE, CONN_STORE)

#: Their roots, as the bindings take them.
ROOTS = tuple(s.root for s in STORES)


def path_set(root: str) -> nu.Nu:
    """``Space.info.path``, the space's root as this process found it. One commit.

    The assembly's to write; ``opened_at`` is the kernel's (its driver).
    """
    return nustd.kv.atomic(Space.info.path.set(root))


def initialized(root: str) -> nu.With:
    """``init`` on the absolute ``root``: see the module for its steps."""
    data = str(data_dir(root))
    locks = [(INFRA_LOCK, "infra"), (KERNEL_LOCK, "kernel"), (WEB_LOCK, "web")]
    flagged = nu.With(nu.Provide(Flagged, {"root": root}), body=nu.Noop())
    return nu.With(
        nu.Provide(Marked, {"root": root}),
        nu.Provide(DataDir, {"root": root, "dirs": DIRS}),
        *(nu.Provide(Lock, {"path": str(Path(data) / f), "what": w}) for f, w in locks),
        binding.quiet(data, ROOTS),
        body=stores.init() >> kernel.init() >> nuspace.web.init() >> path_set(root) >> flagged,
    )


def init(path: str | os.PathLike[str]) -> nu.With:
    """The space at ``path`` made and initialized: every component's init, then the flag. Nothing runs.

    The data dir, ``meta.json``, every store and its containers, the
    kernel's live indexes and system planes, web's planes, made where
    missing; ``Space.info.path`` written; then ``"init": true`` in
    ``meta.json``. No reap, no workers, no driver, no notification server.
    A space already there keeps what it holds: a second init changes
    nothing. Every component's lock is held while it works.

    Raises:
        Refused: An older store format, another assembly's space, or
            infra, a kernel or a web of this space running.
    """
    root, _ = resolve_root(path)
    return initialized(root)


class Prepared:
    """The space at ``root`` initialized at setup, ``init``'s term run to its end. Async only.

    For a throwaway root, which the entry point makes itself: a bracket and
    not a step before the body, so the term keeps what its body yields.

    Args:
        root: The space's root, absolute.
    """

    def __init__(self, root: str) -> None:
        self.root = root

    async def asetup(self, ctx: Context) -> None:
        """Run ``init`` on the root, on its own context."""
        await nu.aeval(nu.compile(initialized(self.root)), nu.Context())


def fresh(root: str, throwaway: bool, term: nu.Nu) -> nu.Nu:
    """``term`` as is, or for a throwaway ``root``: the root made and initialized, ``term``, the root removed."""
    if not throwaway:
        return term
    made = [nu.Provide(Throwaway, {"path": root}), nu.Provide(Prepared, {"root": root})]
    return nu.With(*made, body=term)


def bracketed(
    root: str,
    *,
    locks: Sequence[tuple[str, str]],
    log: tuple[str, str] | None,
    notifier: nu.Nu,
    blobs: Provide | None,
    body: nu.Nu,
) -> nu.With:
    """The brackets of a driver's entry point, from the init check, around ``body``.

    Args:
        root: The space's root, absolute.
        locks: ``(file, what)`` per driver, the file relative to the data dir.
        log: ``(file, what)``, this process's log while it runs, or None.
        notifier: The notification server's bracket, served or joined: the
            stores publish to it.
        blobs: The blob store's spec, or None to bind none.
        body: What runs inside, every store ready.
    """
    data = str(data_dir(root))
    outer: list[nu.Nu] = [
        nu.Provide(Initialized, {"root": root}),
        nu.Provide(DataDir, {"root": root, "dirs": DIRS}),
    ]
    outer += [nu.Provide(Lock, {"path": str(Path(data) / f), "what": w}) for f, w in locks]
    if log is not None:
        outer.append(logged_to(Path(data) / log[0], log[1]))
    outer += [notifier, binding.stores(data, ROOTS)]
    if blobs is not None:
        outer.append(blobs)
    return nu.With(*outer, body=body)
