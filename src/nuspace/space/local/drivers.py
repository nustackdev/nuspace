"""local.infra, local.kernel and local.web: one component each, in the process that runs the term.

A local space runs in three layers, each assuming the ones under it:

- **infra**, what the space runs on: the notification server, owned by
  this process and gone with it (nustd's keeper watches it).
- **kernel**, the kernel's driver. It needs infra up.
- **devices**, web today. It needs the kernel running, so infra too.

The drivers never check what they run on: if infra goes under a kernel,
the kernel fails as it fails. Every check is here, at the entry point,
once, at its start (:func:`~..blocks.required.required`): the kernel refuses
with no infra answering, web with no kernel lock held. Each waits a short
grace for what it needs starting beside it, and the kernel up to
:data:`INFRA_WAIT` seconds while infra's lock is held. A kernel that stops
leaves infra and web up; web's tabs hear again once a kernel is back.

Each takes its own lock, so one of each runs on a space, in one process
or several. None makes or inits a space: each refuses one whose init has
not run (``local.init``). Only infra takes a throwaway root (path None),
which it makes and inits first: nothing else could find it, so the
kernel and web take a path. The kernel and web open the space the same way
(:mod:`.opening`) and meet only through the stores, the notifier and two
files of local's: ``devices/web/session.addr``, where web's tab sessions
answer (:mod:`.session`), and the uploads dir, both named by :mod:`.layout`.

``infra``::

    the init check        refused when meta.json lacks "init": true
    the data dir          local's dirs, made where missing
    infra/infra.lock      one infra per space, or Refused
    infra/infra.log       this process's logging
    the notifier          served, watchdog on: it lives as long as this process
    body                  the body when given, else parked until cancelled

``kernel``, inside the shared brackets::

    path, telemetry       Space.info.path; the open told to telemetry
    worker pool           spare workers, each binding the same stores and blobs
    kernel config         backends, the registry's envs, the session env
                          reading session.addr at every cell run
    race                  the kernel's driver (reap, stamp, system planes,
                          loop, finally close), and the body when given

``web``, inside the shared brackets::

    uploads               the dir wiped: no tab of a web before outlives it
    session.addr          the address picked for the tab sessions, recorded
    race                  web's driver (Conn cleared, nav's old runs stopped,
                          wakes, server and nav), the plane opened on
                          when given, and the body when given

Closing runs the brackets the other way. The kernel's close ends what it
started and left live ``interrupted``; asks stay pending for the next one.

Nothing here runs at build: building a term touches no file. Evaluate it
under a ``if __name__ == "__main__"`` guard: workers are spawned and
re-import the main module.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nuspace.web
from nuspace import kernel as _kernel
from nuspace._telemetry.usage import opened
from nuspace.specs import RegistryWarning, space_registry
from nuspace.web.env import SESSION_ENV

from ..blocks.browse import tab_opened
from ..blocks.guarded import Guarded
from ..blocks.lock import Held, Lock
from ..blocks.logs import logged_to
from ..blocks.meta import data_dir, data_made, resolve_root
from ..blocks.notifier import Answers
from ..blocks.required import required
from ..blocks.workers import DEFAULT_NAME, DEFAULT_SPARES, worker_pool
from . import binding
from .disk import checked, wiped
from .layout import (
    DIRS,
    INFRA_LOCK,
    INFRA_LOG,
    KERNEL_LOCK,
    KERNEL_LOG,
    SESSION_ADDR,
    UPLOADS_DIR,
    WEB_LOCK,
    WEB_LOG,
)
from .opening import ROOTS, bracketed, fresh, path_set
from .plane import found, plane_of
from .session import Recorded, free_address, session_env


if TYPE_CHECKING:
    import os
    from collections.abc import Mapping, Sequence

    from nu.context.fabric import Provide
    from nuspace.kernel import Backend, EnvFactory
    from nuspace.specs import PlaneSpec


__all__ = ["infra", "kernel", "web"]


def merged_envs(registered: Mapping[str, EnvFactory], session: EnvFactory) -> dict[str, EnvFactory]:
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


def infra(path: str | os.PathLike[str] | None = None, *, body: nu.Nu | None = None) -> nu.Nu:
    """The space's infra in this process, run until ``body`` returns, or until cancelled without one.

    Infra is what the space runs on: in local, the notification server. It
    is served with nustd's keeper watching this process, so the server
    lives exactly as long as it: however this process ends, the server
    goes with it. It binds no store: it has nothing of its own to write.
    Logs to ``infra/infra.log``.

    Args:
        path: The space's root, initialized (``local.init``). None is a
            throwaway one, made and initialized here, removed at close.
        body: Nu run inside infra, eg the drivers. Infra stops when it returns.

    Raises:
        Refused: A space not initialized, another assembly's space, or
            infra of this space running already.
    """
    root, throwaway = resolve_root(path)
    data = str(data_dir(root))
    served = nu.With(
        nu.Provide(Lock, {"path": str(Path(data) / INFRA_LOCK), "what": "infra"}),
        logged_to(Path(data) / INFRA_LOG, "infra"),
        binding.served(data),
        body=nu.Park() if body is None else body,
    )
    return fresh(root, throwaway, Guarded(served, checked(root), data_made(root, DIRS)))


def kernel(
    path: str | os.PathLike[str],
    *,
    extensions: Sequence[str] | None = None,
    envs: Mapping[str, EnvFactory] | None = None,
    space_envs: Sequence[Sequence[str] | str] = (),
    backends: Mapping[str, type[Backend]] | None = None,
    spares: int = DEFAULT_SPARES,
    name: str = DEFAULT_NAME,
    blobs: Provide | None = None,
    body: nu.Nu | None = None,
) -> nu.Nu:
    """The space's kernel in this process, run until ``body`` returns, or until cancelled without one.

    See the module for the order. Infra must run on the space: the kernel
    publishes to its notification server, waiting up to :data:`INFRA_WAIT`
    seconds while infra's lock is held, and only :data:`GRACE` seconds
    while it is not. At a clean close (cancelled, or ``body`` returning)
    what the kernel started and left live is ended ``interrupted``. A space
    not initialized, of another store format, another assembly's, or one
    whose kernel runs elsewhere, is refused before anything is written.
    Logs to ``kernel/kernel.log``.

    Args:
        path: The space's root, initialized (``local.init``); its data in
            ``.nuspace/``.
        extensions: The installed packages whose extensions register, by
            entry point name. None registers every installed one, ``()`` none.
        envs: Env factories of the space's own, ahead of every package's.
        space_envs: Env specs every plane run executes inside, outermost.
        backends: Backend classes by name, on top of the built in ``async``
            and ``mp``.
        spares: Idle workers to keep up.
        name: Process name prefix for workers.
        blobs: The blob store (``nuspace.Blobs``): a ``nustd.blob`` spec,
            eg ``nustd.blob.s3(nuspace.Blobs, bucket="models")``. None is
            plain files in ``.nuspace/store/blobs/`` (:func:`~.binding.blobs`).
        body: Nu run beside the kernel. The kernel closes when it returns.

    Raises:
        Refused: A space not initialized, an older store format, another
            assembly's space, no infra running on it, or a kernel of this
            space running already.
    """
    root, _ = resolve_root(path)
    data = str(data_dir(root))
    reg = space_registry(extensions=extensions, envs=envs)
    blobs = binding.blobs(data) if blobs is None else blobs
    factories = merged_envs(reg.envs, session_env(data))
    bindings = binding.stores(data, ROOTS)
    driver = _kernel.driver()
    running = nu.With(
        worker_pool(bindings, blobs, name=name, spares=spares),
        _kernel.bound(backends=backends, envs=factories, space_envs=space_envs),
        body=driver if body is None else nu.Race(driver, body),
    )
    return bracketed(
        root,
        locks=[(KERNEL_LOCK, "kernel")],
        log=(KERNEL_LOG, "kernel"),
        required=needs_infra(data),
        blobs=blobs,
        body=path_set(root) >> opened() >> running,
    )


#: Seconds the kernel waits for infra whose lock is held but whose server is not up yet.
INFRA_WAIT = 30.0

#: Seconds an entry point looks again for what it requires starting beside it, not showing yet.
GRACE = 2.0


def needs_infra(data: str) -> nu.Nu:
    """Infra's notification server answering, or the kernel refused: start infra first."""
    return required(
        Answers(binding.valkey_dir(data)),
        "infra of this space is not running: start it first",
        wait=INFRA_WAIT,
        waiting=Held(str(Path(data) / INFRA_LOCK)),
        grace=GRACE,
    )


def needs_kernel(data: str) -> nu.Nu:
    """The kernel's lock held, or web refused: start the kernel first. A kernel up has infra up."""
    return required(
        Held(str(Path(data) / KERNEL_LOCK)),
        "the kernel of this space is not running: start it first",
        wait=GRACE,
    )


def opened_on(
    spec: PlaneSpec, *, browse: bool = False, host: str = "127.0.0.1", port: int = 8080
) -> nu.Nu:
    """The plane of ``spec`` resolved or made, with ``browse`` a tab opened on it once web answers, then held.

    Args:
        spec: The plane's spec.
        browse: Open a tab on the plane once web at ``host:port`` answers.
        host: Where web binds.
        port: The port web binds.
    """

    def on(plane: nu.ObjectRef) -> nu.Nu:
        steps = [plane_of(spec, plane)]
        if browse:
            # Web's own url, so the tab opens on the same encoded path a link would.
            from nuspace.web.interactions import Href

            url = nu.Str(f"http://{host}:{port}") + nu.Str(Href(plane, {}))
            steps.append(tab_opened(url, host, port))
        return nu.Sequential(*steps, nu.Park())

    return nu.let("", on)


def web(
    path: str | os.PathLike[str],
    *,
    extensions: Sequence[str] | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    static: str | None = "nuspace_ui",
    open_browser: bool = True,
    plane: PlaneSpec | str | None = None,
    blobs: Provide | None = None,
    body: nu.Nu | None = None,
) -> nu.Nu:
    """The space's web in this process, served until ``body`` returns, or until cancelled without one.

    See the module for the order. A kernel must run on the space: web
    looks for its lock held, for up to :data:`GRACE` seconds for one
    coming up, and is refused when there is none. A space not
    initialized, of another store format, another assembly's, or one whose
    web runs elsewhere, is refused before anything is written. Logs to
    ``devices/web/web.log``.

    Args:
        path: The space's root, as :func:`kernel`.
        extensions: The installed packages whose extensions register, as
            :func:`kernel`: the viewer builds user programs from them.
        host: The interface web binds.
        port: The port web binds.
        static: The wheel shipping the browser bundle. None serves the
            socket alone, eg for a vite dev server.
        open_browser: Open a tab once web is up.
        plane: A plane spec, or its registered name (``nudemos.movies``), to
            open on: its newest plane, made from it when there is none, and
            the tab opens on it rather than on home.
        blobs: The blob store, as :func:`kernel`. Both must bind the same.
        body: Nu run beside web. Web stops when it returns.

    Raises:
        Missing: No plane spec of the name ``plane`` (at build).
        Refused: As :func:`kernel`, with web for the kernel; or no kernel
            running on the space.
    """
    root, _ = resolve_root(path)
    data = str(data_dir(root))
    reg = space_registry(extensions=extensions)
    blobs = binding.blobs(data) if blobs is None else blobs
    uploads = str(Path(data) / UPLOADS_DIR)
    address = free_address()
    served = nuspace.web.driver(
        registry=reg,
        host=host,
        port=port,
        static=static,
        open_browser=open_browser and plane is None,
        log_level="warning",
        session_address=address,
        upload_root=uploads,
        blobs=blobs,
    )
    beside = []
    if plane is not None:
        beside.append(opened_on(found(plane), browse=open_browser, host=host, port=port))
    if body is not None:
        beside.append(body)
    recorded = nu.Provide(Recorded, {"path": str(Path(data) / SESSION_ADDR), "address": address})
    running = Guarded(
        nu.With(recorded, body=nu.Race(served, *beside) if beside else served),
        wiped([uploads]),
    )
    return bracketed(
        root,
        locks=[(WEB_LOCK, "web")],
        log=(WEB_LOG, "web"),
        required=needs_kernel(data),
        blobs=blobs,
        body=running,
    )
