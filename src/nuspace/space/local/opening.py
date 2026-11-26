"""What local's entry points share: ``init``, and the steps and brackets from the init check to every store bound.

``init`` makes the space and runs each component's init, once, with
local's mounts of the root and the data dir bound (both made when missing)::

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

    the root              there, or Refused; then local's read only mount of it
    the space checked     through it: no older format, a data dir there
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
before the brackets (``step >> body``); the mounts, the lock, the log and
the stores are brackets, held while the body runs. A
lock held elsewhere is told as local's refusal (:func:`~.disk.told`). The
requirement comes before the lock, so a driver holding its lock has what
it runs on up: web looks only for the kernel's lock. Infra binds no store
and needs nothing: it shares the checks, the mounts, the data dir, a lock
and a log. A throwaway root (path None), which only infra and ``run``
take, is a ``nustd.fs.tmp`` dir whose path, handed to a lambda, the entry
point runs on, its ``init`` first, a step of the same term (:func:`fresh`). Any
entry point takes its root as a term too: every path under it is asked
of the mounts when the term runs.
``open`` shares only the bindings, the mount and the checks: it locks
nothing and makes nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace.web
import nustd.fs
import nustd.kv
from nuspace import kernel
from nuspace.shapes import Space, stores
from nuspace.web.stores import CONN_STORE, WEB_STORE

from ..blocks.logs import logged_to
from ..blocks.meta import resolve_root
from . import binding
from .disk import entered, flagged, marked, told
from .layout import DATA, DIRS, INFRA_LOCK, KERNEL_LOCK, ROOT, WEB_LOCK


if TYPE_CHECKING:
    import os
    from collections.abc import Callable, Sequence

    from nu.context import Provide


__all__ = ["ROOTS", "STORES", "TMP", "bracketed", "fresh", "init", "initialized", "path_set"]


#: Every store local binds: the core ones, then web's.
STORES = (*stores.CORE, WEB_STORE, CONN_STORE)

#: Their roots, as the bindings take them.
ROOTS = tuple(s.root for s in STORES)

#: The tag a throwaway root's temp dir is mounted under.
TMP = nustd.fs.FsRef("nuspace.local.tmp")


def path_set() -> nu.Nu:
    """``Space.info.path``, the space's root as local's mount of it found it. One commit.

    The assembly's to write; ``opened_at`` is the kernel's (its driver).
    """
    return nustd.kv.atomic(Space.info.path.set(ROOT.where()))


def initialized(root: str | nu.Nu) -> nu.Nu:
    """``init`` on ``root``, a path or a term yielding one: see the module for its steps. Yields nothing."""
    locks = [(INFRA_LOCK, "infra"), (KERNEL_LOCK, "kernel"), (WEB_LOCK, "web")]
    inits = stores.init() >> kernel.init() >> nuspace.web.init() >> path_set()
    held = nu.With(
        *(nustd.fs.Lock(DATA / f, w) for f, w in locks),
        binding.quiet(ROOTS),
        body=inits >> flagged(),
    )
    return marked(root, told(DATA.mkdir(*DIRS) >> held))


def init(path: str | os.PathLike[str] | nu.Nu) -> nu.Nu:
    """The space at ``path`` made and initialized: every component's init, then the flag. Nothing runs.

    The root, the data dir, ``meta.json``, every store and its containers, the
    kernel's live indexes and system planes, web's planes, made where
    missing; ``Space.info.path`` written; then ``"init": true`` in
    ``meta.json``. No reap, no workers, no driver, no notification server.
    A space already there keeps what it holds: a second init changes
    nothing. Every component's lock is held while it works.

    Raises:
        Refused: An older store format, another assembly's space, or
            infra, a kernel or a web of this space running.
    """
    return initialized(resolve_root(path))


def fresh(path: str | os.PathLike[str] | nu.Nu | None, on: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """``on(root)``, the term an entry point builds on its root; for ``path`` None on a throwaway one.

    A throwaway root is a ``nustd.fs.tmp`` dir (``nuspace-`` in the
    system's temp dir), initialized first, the term built on the
    ref its lambda hands over the dir's path, the dir removed once all of
    it closed. The path is a plain value in the lambda's frame; a term
    teleported to a worker gets it as a Teleport arg (``watch.in_worker``).
    Yields nothing.
    """
    if path is not None:
        return on(resolve_root(path))
    return nustd.fs.tmp(tag=TMP, prefix="nuspace-", body=lambda root: initialized(root) >> on(root))


def bracketed(
    root: str | nu.Nu,
    *,
    locks: Sequence[tuple[str, str]],
    log: tuple[str, str] | None,
    required: nu.Nu,
    blobs: Provide | None,
    body: nu.Nu,
) -> nu.Nu:
    """The steps and brackets of a driver's entry point, from the init check, around ``body``.

    Yields nothing.

    Args:
        root: The space's root, a path or a term yielding one.
        locks: ``(file, what)`` per driver, the file relative to the data dir,
            taken on local's mount.
        log: ``(file, what)``, this process's log while it runs, or None.
        required: What the driver needs running, looked for before its lock
            (:func:`~..blocks.required.required`): what it requires is up
            by the time it holds its lock.
        blobs: The blob store's spec, or None to bind none.
        body: What runs inside, every store ready.
    """
    held: list[nu.Nu] = [nustd.fs.Lock(DATA / f, w) for f, w in locks]
    if log is not None:
        held.append(logged_to(DATA.where(log[0]), log[1]))
    held.append(binding.stores(ROOTS))
    if blobs is not None:
        held.append(blobs)
    return entered(root, told(required >> DATA.mkdir(*DIRS) >> nu.With(*held, body=body)))
