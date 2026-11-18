"""open_space: a space opened and run in this process, as one term. make_space: one made, nothing run.

The order at open, each step inside the brackets of the ones before::

    meta.json                     an older format refused, another assembly's refused,
                                  written where missing (a space made before it is adopted)
    the data dir                  made, with local's dirs
    kernel.lock                   taken, or Refused: a live kernel holds it
    the notification server
    Space, State                  bound (:mod:`.binding`)
    blobs                         the blob store, plain files in store/blobs/ by default
    format check                  the Space store's format, then the core containers, a commit
                                  per store, then the kernel's live indexes
    device stores                 every device's store bound, its containers, then Conn cleared
                                  by one commit (no tab outlives an open)
    path                          Space.info.path; the open told to telemetry
    device planes                 made where missing
    worker pool                   spare workers, each binding every store of the open, blobs too
    backends, kernel config
    uploads                       the dir wiped, when web is served
    race                          the kernel's driver, each device's driver, the body

The kernel's driver (``nuspace.kernel.driver``) owns the kernel's life:
reap, the ``opened_at`` stamp, the system planes and init's run asked
for, its loop, and ``finally`` the close, which ends what it started
``interrupted`` while the pool and stores are still bound.

Every device's stores open, headless too: a program writing a device's rows
finds them. Only the devices the open names seed their planes and run
their drivers.

Closing runs the brackets the other way: the drivers are cancelled and
drained (each kernel arm lets its workers go, then the kernel's close ends
what it started and left live ``interrupted``, ``kernel.CLOSED``), the
pool stops its workers, the stores close, the server stops, the lock goes.
So the next open's reap finds only what a crash left; a plane run asked
for and never started stays pending, and the next kernel starts it.

Nothing here runs at build: building the term touches no file. Evaluate it
under a ``if __name__ == "__main__"`` guard: workers are spawned and
re-import the main module.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import kernel, system
from nuspace._telemetry.usage import opened
from nuspace.shapes import Space
from nuspace.shapes.stores import CORE
from nuspace.specs import RegistryWarning, space_registry
from nuspace.web.stores import reset_conn

from ..blocks.lock import Lock
from ..blocks.meta import data_dir, resolve_root
from ..blocks.resources import DataDir, Throwaway
from ..blocks.workers import DEFAULT_NAME, DEFAULT_SPARES, worker_pool
from . import binding
from ._disk import Marked, Wiped
from .devices import device, device_stores
from .layout import DIRS, KERNEL_LOCK, UPLOADS_DIR


if TYPE_CHECKING:
    import os
    from collections.abc import Iterable, Mapping, Sequence

    from nu.context.fabric import Provide
    from nuspace.kernel import Backend, EnvFactory
    from nuspace.shapes import Store

    from .devices import Device


__all__ = ["make_space", "open_space"]


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


def _envs(
    registered: Mapping[str, EnvFactory], devices: Mapping[str, Mapping[str, EnvFactory]]
) -> dict[str, EnvFactory]:
    """The registry's env factories with each device's on top: a device owns what it serves."""
    merged = dict(registered)
    for name, envs in devices.items():
        for env, factory in envs.items():
            if env in merged:
                warnings.warn(
                    f"Env {env!r} is the {name} device's, the registered one is ignored",
                    RegistryWarning,
                    stacklevel=4,
                )
            merged[env] = factory
    return merged


def _opening(root: str, throwaway: bool, blobs: Provide | None, body: nu.Nu) -> nu.With:
    """The brackets every open shares, from the data dir to every device's stores, around ``body``.

    ``body`` runs with every store open and initialized: the format checked,
    Conn cleared, the blob store bound (unless ``blobs``
    is None: nothing runs). Every device's stores, whichever devices the
    open serves.
    """
    data = str(data_dir(root))
    extra = device_stores()
    inner = _inits(extra) >> nustd.kv.atomic(reset_conn()) >> body
    if extra:
        inner = nu.With(binding.stores(data, [s.root for s in extra]), body=inner)
    outer = [
        nu.Provide(Marked, {"root": root}),
        nu.Provide(DataDir, {"root": root, "dirs": DIRS}),
        nu.Provide(Lock, {"path": str(Path(data) / KERNEL_LOCK)}),
        binding.notifier(data),
        binding.stores(data, [s.root for s in CORE]),
    ]
    if blobs is not None:
        outer.append(blobs)
    if throwaway:
        outer.insert(0, nu.Provide(Throwaway, {"path": root}))
    live = nustd.kv.atomic(kernel.init_live())
    return nu.With(*outer, body=_inits(CORE) >> live >> inner)


def _seeds(devices: Sequence[Device]) -> nu.Nu:
    """Each device's planes, made where missing. The system planes are the kernel's."""
    return nu.Sequential(*(d.seed() for d in devices))


def open_space(
    path: str | os.PathLike[str] | None = None,
    *,
    devices: Sequence[str] = ("web",),
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

    The kernel, the system planes and each device run; see the module for
    the order. Every device's stores open, served or not. At a clean close
    (cancelled, or ``body`` returning) everything still live is ended
    ``interrupted`` before the stores close. A space of another store
    format, another assembly's, or one a live kernel holds, is refused before
    anything is written.

    Args:
        path: The space's root, any directory, made if missing; its data in
            ``.nuspace/``. None is a throwaway one, removed at close.
        devices: The devices to serve, by name: each seeds its planes and
            runs its driver. ``("web",)`` serves the browser, ``()`` is
            headless. Every device's stores open either way.
        host: The interface the web device binds.
        port: The port the web device binds.
        open_browser: The web device opens a tab once it is up.
        static: The wheel shipping the browser bundle. None serves the
            socket alone, eg for a vite dev server.
        spares: Idle workers to keep up.
        extensions: The installed packages whose extensions register, by
            entry point name. None registers every installed one, ``()`` none.
        envs: Env factories of the host's own, ahead of every package's.
        space_envs: Env specs every plane run executes inside, outermost.
        backends: Backend classes by name, on top of the built in ``async``
            and ``mp``.
        blobs: The blob store (``nuspace.Blobs``): a ``nustd.blob`` spec,
            eg ``nustd.blob.s3(nuspace.Blobs, bucket="models")``. None is
            plain files in ``.nuspace/store/blobs/``
            (:func:`~.binding.blobs`).
        body: Host nu run beside the drivers. The space closes when it returns.
        name: Process name prefix for workers.

    Raises:
        Missing: A device of no known name (at build).
        Refused: An older store format, another assembly's space, or the
            space open in another kernel.
    """
    root, throwaway = resolve_root(path)
    data = str(data_dir(root))
    opened_devices = [device(d) for d in devices]
    reg = space_registry(extensions=extensions, envs=envs)
    blobs = binding.blobs(data) if blobs is None else blobs
    uploads = str(Path(data) / UPLOADS_DIR)
    options = {
        "host": host,
        "port": port,
        "static": static,
        "open_browser": open_browser,
        "upload_root": uploads,
        "blobs": blobs,
    }
    served = {d.name: d.serve(registry=reg, **options) for d in opened_devices}
    factories = _envs(reg.envs, {n: e for n, (_, e) in served.items()})
    bindings = binding.stores(data, [s.root for s in (*CORE, *device_stores())])
    drivers = nu.Race(
        kernel.driver(), *(t for t, _ in served.values()), nu.Park() if body is None else body
    )
    running = nu.With(
        worker_pool(bindings, blobs, name=name, spares=spares),
        kernel.bound(backends=backends, envs=factories, space_envs=space_envs),
        body=drivers,
    )
    if "web" in served:
        running = nu.With(nu.Provide(Wiped, {"dirs": [uploads]}), body=running)
    return _opening(
        root, throwaway, blobs, _path(root) >> opened() >> _seeds(opened_devices) >> running
    )


def make_space(path: str | os.PathLike[str], *, devices: Sequence[str] = ("web",)) -> nu.With:
    """The space at ``path`` made and seeded as its first open would, then closed. Nothing runs.

    The data dir, the lock, every store and its containers (every
    device's too, and the kernel's live indexes), the system planes and
    each named device's planes, made where missing. No reap, no workers, no
    driver. A space already there is left as it is.

    Raises:
        Missing: A device of no known name (at build).
        Refused: An older store format, another assembly's space, or the
            space open in another kernel.
    """
    root, _ = resolve_root(path)
    opened_devices = [device(d) for d in devices]
    return _opening(root, False, None, system.ensure() >> _seeds(opened_devices))
