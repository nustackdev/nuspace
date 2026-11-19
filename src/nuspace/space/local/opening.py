"""What local's entry points share: ``init``, and the steps and brackets from the init check to every store bound.

``init`` makes the space and runs each component's init, once, with
local's mount of the data dir bound (made when missing)::

    meta.json             an older format refused, another assembly's refused,
                          written where missing (a space made before it is adopted)
    the data dir          local's dirs, made where missing
    locks                 infra's, the kernel's, web's: refused while any runs
    Space, State, Web, Conn   bound quiet: nothing runs, so nobody listens
    inits                 core's (the Space format checked first), the
                          kernel's, web's, each its own commits
    Space.info.path       the space's root
    "init": true          in meta.json, last: a failed init leaves it false

The kernel and web open the space the same way after it, each step
inside the brackets of the ones before::

    the space checked     before the mount: no older format, a data dir there
    the mount             local's, over the data dir, never making it
    the init check        refused when meta.json lacks "init": true
    the requirement       what the driver runs on, up, or Refused: infra
                          for the kernel, the kernel for web
    the data dir          local's dirs, made where missing
    lock                  the driver's (``nustd.fs.Lock``), or Refused
    log                   this process's logging at the driver's file
    Space, State, Web, Conn   bound (:mod:`.binding`), publishing to
                          infra's notification server
    blobs                 when the entry point binds them

The checks, the requirement and the data dir are steps, run in order
before the brackets (:class:`~..blocks.guarded.Guarded`); the mount, the
lock, the log and the stores are brackets, held while the body runs. A
lock held elsewhere is told as local's refusal (:func:`~.disk.told`). The
requirement comes before the lock, so a driver holding its lock has what
it runs on up: web looks only for the kernel's lock. Infra binds no store
and needs nothing: it shares the checks, the mount, the data dir, a lock
and a log. A throwaway root (path None), which only infra and ``run``
take, is made by the entry point itself, so its ``init`` runs first, a
step of the same term (:func:`fresh`).
``open`` shares only the bindings, the mount and the checks: it locks
nothing and makes nothing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nuspace.web
import nustd.fs
import nustd.kv
from nuspace import kernel
from nuspace.shapes import Space, stores
from nuspace.web.stores import CONN_STORE, WEB_STORE

from ..blocks.guarded import Guarded
from ..blocks.logs import logged_to
from ..blocks.meta import data_dir, resolve_root
from ..blocks.resources import throwaway
from . import binding
from .disk import entered, flagged, marked, told
from .layout import DATA, DIRS, INFRA_LOCK, KERNEL_LOCK, WEB_LOCK


if TYPE_CHECKING:
    import os
    from collections.abc import Sequence

    from nu.context.fabric import Provide


__all__ = ["ROOTS", "STORES", "bracketed", "fresh", "init", "initialized", "path_set"]


#: Every store local binds: the core ones, then web's.
STORES = (*stores.CORE, WEB_STORE, CONN_STORE)

#: Their roots, as the bindings take them.
ROOTS = tuple(s.root for s in STORES)


def path_set(root: str) -> nu.Nu:
    """``Space.info.path``, the space's root as this process found it. One commit.

    The assembly's to write; ``opened_at`` is the kernel's (its driver).
    """
    return nustd.kv.atomic(Space.info.path.set(root))


def initialized(root: str) -> nu.Nu:
    """``init`` on the absolute ``root``: see the module for its steps. Yields nothing."""
    data = str(data_dir(root))
    locks = [(INFRA_LOCK, "infra"), (KERNEL_LOCK, "kernel"), (WEB_LOCK, "web")]
    inits = stores.init() >> kernel.init() >> nuspace.web.init() >> path_set(root)
    held = nu.With(
        *(nustd.fs.Lock(DATA / f, w) for f, w in locks),
        binding.quiet(data, ROOTS),
        body=inits >> flagged(root),
    )
    return marked(root, told(DATA.mkdir(*DIRS) >> held))


def init(path: str | os.PathLike[str]) -> nu.Nu:
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


def fresh(root: str, throwaway_root: bool, term: nu.Nu) -> nu.Nu:
    """``term`` as is, or for a throwaway ``root``: the root made and initialized, ``term``, the root removed.

    Yields what ``term`` yields.
    """
    if not throwaway_root:
        return term
    return throwaway(root, Guarded(term, initialized(root)))


def bracketed(
    root: str,
    *,
    locks: Sequence[tuple[str, str]],
    log: tuple[str, str] | None,
    required: nu.Nu,
    blobs: Provide | None,
    body: nu.Nu,
) -> nu.Nu:
    """The steps and brackets of a driver's entry point, from the init check, around ``body``.

    Yields what ``body`` yields.

    Args:
        root: The space's root, absolute.
        locks: ``(file, what)`` per driver, the file relative to the data dir,
            taken on local's mount.
        log: ``(file, what)``, this process's log while it runs, or None.
        required: What the driver needs running, looked for before its lock
            (:func:`~..blocks.required.required`): what it requires is up
            by the time it holds its lock.
        blobs: The blob store's spec, or None to bind none.
        body: What runs inside, every store ready.
    """
    data = str(data_dir(root))
    held: list[nu.Nu] = [nustd.fs.Lock(DATA / f, w) for f, w in locks]
    if log is not None:
        held.append(logged_to(Path(data) / log[0], log[1]))
    held.append(binding.stores(data, ROOTS))
    if blobs is not None:
        held.append(blobs)
    return entered(root, told(Guarded(nu.With(*held, body=body), required, DATA.mkdir(*DIRS))))
