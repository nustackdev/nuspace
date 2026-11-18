"""open_space: a space opened and run in this process, as one term. make_space: one made, nothing run.

The order at open, each step inside the brackets of the ones before::

    meta.json                     an older format refused, another assembly's refused,
                                  written where missing (a space made before it is adopted)
    the data dir                  made, with local's dirs
    kernel.lock                   taken, or Refused: a live kernel holds it
    the notification server
    Space, State, Web, Conn       bound (:mod:`.binding`)
    blobs                         the blob store, plain files in store/blobs/ by default
    format check                  the Space store's format, then each store's containers,
                                  a commit per store, then the kernel's live indexes
    path                          Space.info.path; the open told to telemetry
    worker pool                   spare workers, each binding every store of the open, blobs too
    backends, kernel config       the session env reading session.addr (:mod:`._session`)
    uploads, session.addr         the dir wiped, the address web picked written, when served
    race                          the kernel's driver, web's driver when served, the body

The kernel's driver (``nuspace.kernel.driver``) owns the kernel's life:
reap, the ``opened_at`` stamp, the system planes and init's run asked
for, its loop, and ``finally`` the close. Web's driver
(``nuspace.web.driver``) owns web's: Conn cleared, the runs nav asked
for before stopped, its planes, then the server and nav.

Every store opens, headless too: a program writing a web row finds it.

Closing runs the brackets the other way: the drivers are cancelled and
drained (each kernel arm lets its workers go, then the kernel's close ends
what it started and left live ``interrupted``, ``kernel.CLOSED``), the
pool stops its workers, the stores close, the server stops, the lock goes.
So the next open's reap finds only what a crash left; a plane run asked
for and never started stays pending, and the next kernel starts it.

One process for now: the real entry points (``local.kernel``,
``local.web``) split this in two.

Nothing here runs at build: building the term touches no file. Evaluate it
under a ``if __name__ == "__main__"`` guard: workers are spawned and
re-import the main module.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nuspace.web
import nustd.kv
from nuspace import kernel, system
from nuspace._telemetry.usage import opened
from nuspace.shapes import Space
from nuspace.shapes.stores import CORE
from nuspace.specs import RegistryWarning, space_registry
from nuspace.web.env import SESSION_ENV
from nuspace.web.planes import ensure as web_planes
from nuspace.web.stores import CONN_STORE, WEB_STORE

from ..blocks.lock import Lock
from ..blocks.meta import data_dir, resolve_root
from ..blocks.resources import DataDir, Throwaway
from ..blocks.workers import DEFAULT_NAME, DEFAULT_SPARES, worker_pool
from . import binding
from ._disk import Marked, Wiped
from ._session import Recorded, free_address, session_env
from .layout import DIRS, KERNEL_LOCK, SESSION_ADDR, UPLOADS_DIR


if TYPE_CHECKING:
    import os
    from collections.abc import Iterable, Mapping, Sequence

    from nu.context.fabric import Provide
    from nuspace.kernel import Backend, EnvFactory
    from nuspace.shapes import Store


__all__ = ["make_space", "open_space"]


#: Every store an open binds: the core ones, then web's.
STORES = (*CORE, WEB_STORE, CONN_STORE)


def _inits(stores: Iterable[Store]) -> nu.Nu:
    """Each store's fixed containers made where missing, one commit per store, in order."""
    return nu.Sequential(*(nustd.kv.atomic(s.init()) for s in stores))


def _path(root: str) -> nu.Nu:
    """``Space.info.path``, the space's root as this open found it. One commit.

    The assembly's to write; ``opened_at`` is the kernel's (its driver).

    Args:
        root: The space's root, absolute.
    """
    return nustd.kv.atomic(Space.info.path.set(root))


def _envs(registered: Mapping[str, EnvFactory], session: EnvFactory) -> dict[str, EnvFactory]:
    """The registry's env factories with web's session env on top: web owns what it serves."""
    merged = dict(registered)
    if SESSION_ENV in merged:
        warnings.warn(
            f"Env {SESSION_ENV!r} is web's, the registered one is ignored",
            RegistryWarning,
            stacklevel=4,
        )
    merged[SESSION_ENV] = session
    return merged


def _opening(root: str, throwaway: bool, blobs: Provide | None, body: nu.Nu) -> nu.With:
    """The brackets every open shares, from the data dir to every store, around ``body``.

    ``body`` runs with every store open and initialized: the format checked,
    the blob store bound (unless ``blobs`` is None: nothing runs).
    """
    data = str(data_dir(root))
    outer = [
        nu.Provide(Marked, {"root": root}),
        nu.Provide(DataDir, {"root": root, "dirs": DIRS}),
        nu.Provide(Lock, {"path": str(Path(data) / KERNEL_LOCK)}),
        binding.notifier(data),
        binding.stores(data, [s.root for s in STORES]),
    ]
    if blobs is not None:
        outer.append(blobs)
    if throwaway:
        outer.insert(0, nu.Provide(Throwaway, {"path": root}))
    core, web = _inits(CORE), _inits((WEB_STORE, CONN_STORE))
    live = nustd.kv.atomic(kernel.init_live())
    return nu.With(*outer, body=core >> live >> web >> body)


def open_space(
    path: str | os.PathLike[str] | None = None,
    *,
    web: bool = True,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    static: str | None = "nuspace_ui",
    spares: int = DEFAULT_SPARES,
    extensions: Sequence[str] | None = None,
    envs: Mapping[str, EnvFactory] | None = None,
    space_envs: Sequence[Sequence[str] | str] = (),
    backends: Mapping[str, type[Backend]] | None = None,
    blobs: Provide | None = None,
    body: nu.Nu | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A space opened in this process, run until ``body`` returns, or until cancelled without one.

    The kernel, the system planes and, served, web run; see the module for
    the order. Every store opens, served or not. At a clean close
    (cancelled, or ``body`` returning) everything still live is ended
    ``interrupted`` before the stores close. A space of another store
    format, another assembly's, or one a live kernel holds, is refused before
    anything is written.

    Args:
        path: The space's root, any directory, made if missing; its data in
            ``.nuspace/``. None is a throwaway one, removed at close.
        web: Serve the browser: web's driver runs beside the kernel's.
            False is headless; web's stores open either way.
        host: The interface web binds.
        port: The port web binds.
        open_browser: Web opens a tab once it is up.
        static: The wheel shipping the browser bundle. None serves the
            socket alone, eg for a vite dev server.
        spares: Idle workers to keep up.
        extensions: The installed packages whose extensions register, by
            entry point name. None registers every installed one, ``()`` none.
        envs: Env factories of the open's own, ahead of every package's.
        space_envs: Env specs every plane run executes inside, outermost.
        backends: Backend classes by name, on top of the built in ``async``
            and ``mp``.
        blobs: The blob store (``nuspace.Blobs``): a ``nustd.blob`` spec,
            eg ``nustd.blob.s3(nuspace.Blobs, bucket="models")``. None is
            plain files in ``.nuspace/store/blobs/``
            (:func:`~.binding.blobs`).
        body: Nu run beside the drivers. The space closes when it returns.
        name: Process name prefix for workers.

    Raises:
        Refused: An older store format, another assembly's space, or the
            space open in another kernel.
    """
    root, throwaway = resolve_root(path)
    data = str(data_dir(root))
    reg = space_registry(extensions=extensions, envs=envs)
    blobs = binding.blobs(data) if blobs is None else blobs
    factories = _envs(reg.envs, session_env(data))
    bindings = binding.stores(data, [s.root for s in STORES])
    drivers = [kernel.driver()]
    if web:
        uploads = str(Path(data) / UPLOADS_DIR)
        address = free_address()
        served = nuspace.web.driver(
            registry=reg,
            host=host,
            port=port,
            static=static,
            open_browser=open_browser,
            log_level="warning",
            session_address=address,
            upload_root=uploads,
        )
        recorded = nu.Provide(
            Recorded, {"path": str(Path(data) / SESSION_ADDR), "address": address}
        )
        drivers.append(nu.With(nu.Provide(Wiped, {"dirs": [uploads]}), recorded, body=served))
    running = nu.With(
        worker_pool(bindings, blobs, name=name, spares=spares),
        kernel.bound(backends=backends, envs=factories, space_envs=space_envs),
        body=nu.Race(*drivers, nu.Park() if body is None else body),
    )
    return _opening(root, throwaway, blobs, _path(root) >> opened() >> running)


def make_space(path: str | os.PathLike[str]) -> nu.With:
    """The space at ``path`` made and seeded as its first open would, then closed. Nothing runs.

    The data dir, the lock, every store and its containers (the kernel's
    live indexes too), the system planes and web's planes, made where
    missing. No reap, no workers, no driver. A space already there is left
    as it is.

    Raises:
        Refused: An older store format, another assembly's space, or the
            space open in another kernel.
    """
    root, _ = resolve_root(path)
    return _opening(root, False, None, system.ensure() >> web_planes())
