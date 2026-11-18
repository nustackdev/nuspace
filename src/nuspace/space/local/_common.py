"""What local's entry points share: the brackets from the space's mark to every store bound.

Every entry point that runs a driver, and ``init``, opens a space the same
way, each step inside the brackets of the ones before::

    throwaway             the root, made, removed at the end (path None only)
    meta.json             an older format refused, another assembly's refused,
                          written where missing (a space made before it is adopted)
    the data dir          made, with local's dirs
    locks                 one per driver the entry point runs, or Refused
    log                   this process's logging at the driver's file
    the notifier          the kernel's: started and owned by the kernel,
                          joined by web (refused with no kernel up), none
                          for init (nobody to hear it)
    Space, State, Web, Conn   bound (:mod:`.binding`), publishing when a
                          notifier is there, quiet when not
    blobs                 when the entry point binds them
    inits                 the Space store's format, each store's containers,
                          a commit per store, the kernel's live indexes too

``open`` shares only the bindings: it marks, locks, inits nothing, and
publishes only when a kernel's server answers.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import kernel
from nuspace.shapes import Space
from nuspace.shapes.stores import CORE
from nuspace.web.stores import CONN_STORE, WEB_STORE

from ..blocks.lock import Lock
from ..blocks.logs import logs
from ..blocks.meta import data_dir
from ..blocks.resources import DataDir, Throwaway
from . import binding
from ._disk import Marked
from .layout import DIRS


if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from nu.context.fabric import Provide
    from nuspace.shapes import Store


__all__ = ["ROOTS", "STORES", "inits", "opening", "path_set"]


#: Every store local binds: the core ones, then web's.
STORES = (*CORE, WEB_STORE, CONN_STORE)

#: Their roots, as the bindings take them.
ROOTS = tuple(s.root for s in STORES)


def _each(stores: Iterable[Store]) -> nu.Nu:
    """Each store's fixed containers made where missing, one commit per store, in order."""
    return nu.Sequential(*(nustd.kv.atomic(s.init()) for s in stores))


def inits() -> nu.Nu:
    """Every store ready: the core ones (the format checked first), the live indexes, web's."""
    return _each(CORE) >> nustd.kv.atomic(kernel.init_live()) >> _each((WEB_STORE, CONN_STORE))


def path_set(root: str) -> nu.Nu:
    """``Space.info.path``, the space's root as this process found it. One commit.

    The assembly's to write; ``opened_at`` is the kernel's (its driver).
    """
    return nustd.kv.atomic(Space.info.path.set(root))


def opening(
    root: str,
    *,
    throwaway: bool,
    locks: Sequence[tuple[str, str]],
    log: tuple[str, str] | None,
    notifier: nu.Nu | None,
    blobs: Provide | None,
    body: nu.Nu,
) -> nu.With:
    """The brackets of the module's list around ``body``, which runs with every store ready.

    Args:
        root: The space's root, absolute.
        throwaway: Make the root, and remove it with everything in it at the end.
        locks: ``(file, what)`` per driver, the file relative to the data dir.
        log: ``(file, what)``, this process's log while it runs, or None.
        notifier: The notification server's bracket, served or joined: the
            stores publish to it. None binds them quiet.
        blobs: The blob store's spec, or None to bind none.
        body: What runs inside, after the inits.
    """
    data = str(data_dir(root))
    outer: list[nu.Nu] = []
    if throwaway:
        outer.append(nu.Provide(Throwaway, {"path": root}))
    outer += [
        nu.Provide(Marked, {"root": root}),
        nu.Provide(DataDir, {"root": root, "dirs": DIRS}),
    ]
    outer += [nu.Provide(Lock, {"path": str(Path(data) / f), "what": w}) for f, w in locks]
    if log is not None:
        outer.append(logs(Path(data) / log[0], log[1]))
    if notifier is None:
        outer.append(binding.quiet(data, ROOTS))
    else:
        outer += [notifier, binding.stores(data, ROOTS)]
    if blobs is not None:
        outer.append(blobs)
    return nu.With(*outer, body=inits() >> body)
