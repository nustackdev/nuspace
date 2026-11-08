"""open_space: a space opened and run in this process, as one term. make_space: one made, nothing run.

The order at open, each step inside the brackets of the ones before::

    the data dir                  made; a space of an older format refused
    host.lock                     taken, or Refused: a live host holds it
    the notification server
    Space, State                  their navigators
    format check                  space.db's format, then the core containers, a commit per store
    fresh device stores           conn.db deleted, then the device navigators, their containers
    reap                          what a dead host left live, ended killed
    stamp                         Space.info path and opened_at; the open told to telemetry
    system and device planes      made where missing
    worker pool                   spare workers, each binding every store of the open
    backends, kernel config
    init's plane run asked for
    race                          the kernel, each device's driver, the body

Closing runs the brackets the other way: the drivers are cancelled, the
pool stops its workers, the stores close, the server stops, the lock goes.

Nothing here runs at build: building the term touches no file. Evaluate it
under a ``if __name__ == "__main__"`` guard: workers are spawned and
re-import the main module.
"""

from __future__ import annotations

import tempfile
import uuid
import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.kv
import nustd.mp_pool
import nustd.time
from nuspace import kernel, system
from nuspace._telemetry.usage import opened
from nuspace.shapes import Space
from nuspace.specs import RegistryWarning, space_registry

from .devices import device
from .layout import LOCK_FILE, data_dir
from .lock import HostLock
from .resources import DataDir, Fresh, Throwaway, Warmed
from .stores import CORE, navigators, notifier


if TYPE_CHECKING:
    import os
    from collections.abc import Iterable, Mapping, Sequence

    from nuspace.kernel import Backend, EnvFactory
    from nuspace.shapes import Store

    from .devices import Device


__all__ = [
    "DEFAULT_GRACE",
    "DEFAULT_NAME",
    "DEFAULT_SPARES",
    "make_space",
    "open_space",
    "stamp",
    "worker_context",
    "worker_pool",
]


#: Process name prefix for the pool's workers, so a space shows in a process list.
DEFAULT_NAME = "nuspace"

#: How many idle workers the pool keeps up: one for the plane being opened,
#: one for the tab beside it.
DEFAULT_SPARES = 2

#: Seconds a worker gets to end once let go, or when the space closes: torn
#: down politely, killed past it.
DEFAULT_GRACE = 2.0


def _root(path: str | os.PathLike[str] | None) -> tuple[str, bool]:
    """The space's root, absolute, and whether it is a throwaway one.

    A throwaway root is only named here, in the temp dir; :class:`Throwaway`
    makes it at open and removes it at close.
    """
    if path is None:
        return str(Path(tempfile.gettempdir()) / f"nuspace-{uuid.uuid4().hex[:8]}"), True
    return str(Path(path).expanduser().resolve()), False


def _inits(stores: Iterable[Store]) -> nu.Nu:
    """Each store's fixed containers made where missing, one commit per store, in order."""
    return nu.Sequential(*(nustd.kv.atomic(s.init()) for s in stores))


def stamp(root: str) -> nu.Nu:
    """``Space.info.path`` and ``opened_at`` for this open. One commit.

    Before the drivers: init reads ``opened_at`` to tell a run of this open
    from an older one.

    Args:
        root: The space's root, absolute.
    """
    info = Space.info
    return nustd.kv.atomic(info.path.set(root) >> info.opened_at.set(nustd.time.time()))


def worker_context(data: str, stores: Sequence[Store]) -> nu.With:
    """What every worker comes up holding. Pickled to the child, entered there.

    Process scope only, since the pool pays it on every launch: every store
    of the open, opened by the worker itself on the host's files and server,
    a dict for host local records, and the warm module cache. Whatever one
    run needs rides in its body.

    Args:
        data: The space's data dir, absolute.
        stores: The stores of the open, core ones and the devices'.
    """
    return nu.With(navigators(data, stores), nu.Provide(dict, {}), nu.Provide(Warmed, {}))


def worker_pool(
    data: str,
    stores: Sequence[Store],
    *,
    name: str = DEFAULT_NAME,
    spares: int = DEFAULT_SPARES,
    grace: float = DEFAULT_GRACE,
) -> nu.Provide:
    """The fleet, every worker holding :func:`worker_context`. Closing stops them all.

    Args:
        data: The space's data dir, absolute.
        stores: The stores every worker binds.
        name: Process name prefix.
        spares: Idle workers to keep up, so a launch does not wait for a spawn.
        grace: Seconds a worker gets to end, polite first, killed past it.
    """
    return nustd.mp_pool.pool(
        name=name, init=worker_context(data, stores), spares=spares, grace=grace
    )


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


def _opening(root: str, throwaway: bool, devices: Sequence[Device], body: nu.Nu) -> nu.With:
    """The brackets every open shares, from the data dir to the device stores, around ``body``.

    ``body`` runs with every store open and initialized: the format checked,
    the fresh stores made again.
    """
    data = str(data_dir(root))
    extra = tuple(s for d in devices for s in d.stores)
    files = [s.file for s in (*CORE, *extra)]
    inner = _inits(extra) >> body
    if extra:
        fresh = [str(Path(data) / s.file) for s in extra if s.fresh]
        inner = nu.With(nu.Provide(Fresh, {"paths": fresh}), navigators(data, extra), body=inner)
    outer = [
        nu.Provide(DataDir, {"root": root, "files": files}),
        nu.Provide(HostLock, {"path": str(Path(data) / LOCK_FILE)}),
        notifier(data),
        navigators(data, CORE),
    ]
    if throwaway:
        outer.insert(0, nu.Provide(Throwaway, {"path": root}))
    return nu.With(*outer, body=_inits(CORE) >> inner)


def _seeds(devices: Sequence[Device]) -> nu.Nu:
    """The system planes, then each device's, made where missing."""
    return nu.Sequential(system.ensure(), *(d.seed() for d in devices))


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
    body: nu.Nu | None = None,
    name: str = DEFAULT_NAME,
) -> nu.With:
    """A space opened in this process, run until ``body`` returns, or until cancelled without one.

    The kernel, the system planes and each device run; see the module for
    the order. A space of another store format, or one a live host holds,
    is refused before anything is written.

    Args:
        path: The space's root, any directory, made if missing; its data in
            ``.nuspace/``. None is a throwaway one, removed at close.
        devices: The devices to open it with, by name: ``("web",)`` serves
            the browser, ``()`` is headless.
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
        body: Host nu run beside the drivers. The space closes when it returns.
        name: Process name prefix for workers.

    Raises:
        Missing: A device of no known name (at build).
        Refused: An older store format, or the space open in another host.
    """
    root, throwaway = _root(path)
    data = str(data_dir(root))
    opened_devices = [device(d) for d in devices]
    reg = space_registry(extensions=extensions, envs=envs)
    options = {"host": host, "port": port, "static": static, "open_browser": open_browser}
    served = {d.name: d.serve(registry=reg, **options) for d in opened_devices}
    factories = _envs(reg.envs, {n: e for n, (_, e) in served.items()})
    stores = (*CORE, *(s for d in opened_devices for s in d.stores))
    drivers = nu.Race(
        kernel.kernel(), *(t for t, _ in served.values()), nu.Park() if body is None else body
    )
    running = nu.With(
        worker_pool(data, stores, name=name, spares=spares),
        kernel.bound(backends=backends, envs=factories, space_envs=space_envs),
        body=system.start() >> drivers,
    )
    return _opening(
        root,
        throwaway,
        opened_devices,
        kernel.reap() >> stamp(root) >> opened() >> _seeds(opened_devices) >> running,
    )


def make_space(path: str | os.PathLike[str], *, devices: Sequence[str] = ("web",)) -> nu.With:
    """The space at ``path`` made and seeded as its first open would, then closed. Nothing runs.

    The data dir, the lock, the stores and their containers, the system
    planes and each device's planes, made where missing. No reap, no
    workers, no driver. A space already there is left as it is.

    Raises:
        Missing: A device of no known name (at build).
        Refused: An older store format, or the space open in another host.
    """
    root, _ = _root(path)
    opened_devices = [device(d) for d in devices]
    return _opening(root, False, opened_devices, _seeds(opened_devices))
