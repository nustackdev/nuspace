"""local.kernel and local.web: one driver each, in the process that runs the term.

Both open the space the same way (:mod:`._common`), each under its own
lock, so one kernel and one web run on a space, in one process or two, in
any order. They meet only through the stores, the notifier and two files
of local's: ``devices/web/session.addr``, where web's tab sessions answer
(:mod:`._session`), and the uploads dir, both named by :mod:`.layout`.

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
                          its planes, server and nav), the plane opened on
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

from ..blocks.browse import Browse
from ..blocks.meta import data_dir, resolve_root
from ..blocks.workers import DEFAULT_NAME, DEFAULT_SPARES, worker_pool
from . import binding
from ._common import STORES, opening, path_set
from ._disk import Wiped
from ._plane import found, plane_of
from ._session import Recorded, free_address, session_env
from .layout import KERNEL_LOCK, KERNEL_LOG, SESSION_ADDR, UPLOADS_DIR, WEB_LOCK, WEB_LOG


if TYPE_CHECKING:
    import os
    from collections.abc import Mapping, Sequence

    from nu.context.fabric import Provide
    from nuspace.kernel import Backend, EnvFactory
    from nuspace.specs import PlaneSpec


__all__ = ["kernel", "web"]


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


def kernel(
    path: str | os.PathLike[str] | None = None,
    *,
    extensions: Sequence[str] | None = None,
    envs: Mapping[str, EnvFactory] | None = None,
    space_envs: Sequence[Sequence[str] | str] = (),
    backends: Mapping[str, type[Backend]] | None = None,
    spares: int = DEFAULT_SPARES,
    name: str = DEFAULT_NAME,
    blobs: Provide | None = None,
    body: nu.Nu | None = None,
) -> nu.With:
    """The space's kernel in this process, run until ``body`` returns, or until cancelled without one.

    See the module for the order. At a clean close (cancelled, or ``body``
    returning) what the kernel started and left live is ended
    ``interrupted``. A space of another store format, another assembly's,
    or one whose kernel runs elsewhere, is refused before anything is
    written. Logs to ``kernel/kernel.log``.

    Args:
        path: The space's root, any directory, made if missing; its data in
            ``.nuspace/``. None is a throwaway one, removed at close.
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
        Refused: An older store format, another assembly's space, or a
            kernel of this space running already.
    """
    root, throwaway = resolve_root(path)
    data = str(data_dir(root))
    reg = space_registry(extensions=extensions, envs=envs)
    blobs = binding.blobs(data) if blobs is None else blobs
    factories = _envs(reg.envs, session_env(data))
    bindings = binding.stores(data, [s.root for s in STORES])
    driver = _kernel.driver()
    running = nu.With(
        worker_pool(bindings, blobs, name=name, spares=spares),
        _kernel.bound(backends=backends, envs=factories, space_envs=space_envs),
        body=driver if body is None else nu.Race(driver, body),
    )
    return opening(
        root,
        throwaway=throwaway,
        locks=[(KERNEL_LOCK, "kernel")],
        log=(KERNEL_LOG, "kernel"),
        blobs=blobs,
        body=path_set(root) >> opened() >> running,
    )


def _opened_on(spec: PlaneSpec, host: str, port: int, browse: bool) -> nu.Nu:
    """The plane of ``spec`` resolved or made, a tab opened on it once web answers, then held."""

    def on(plane: nu.ObjectRef) -> nu.Nu:
        steps = [plane_of(spec, plane)]
        if browse:
            # Web's own url, so the tab opens on the same encoded path a link would.
            from nuspace.web.interactions import Href

            url = nu.Str(f"http://{host}:{port}") + nu.Str(Href(plane, {}))
            steps.append(Browse(url, host, port))
        return nu.Sequential(*steps, nu.Park())

    return nu.let("", on)


def web(
    path: str | os.PathLike[str] | None = None,
    *,
    extensions: Sequence[str] | None = None,
    host: str = "127.0.0.1",
    port: int = 8080,
    static: str | None = "nuspace_ui",
    open_browser: bool = True,
    plane: PlaneSpec | str | None = None,
    blobs: Provide | None = None,
    body: nu.Nu | None = None,
) -> nu.With:
    """The space's web in this process, served until ``body`` returns, or until cancelled without one.

    See the module for the order. No kernel needs to run: what web asks
    for (nav's plane runs) waits pending until one does. A space of
    another store format, another assembly's, or one whose web runs
    elsewhere, is refused before anything is written. Logs to
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
        Refused: As :func:`kernel`, with web for the kernel.
    """
    root, throwaway = resolve_root(path)
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
    )
    beside = [] if plane is None else [_opened_on(found(plane), host, port, open_browser)]
    if body is not None:
        beside.append(body)
    recorded = nu.Provide(Recorded, {"path": str(Path(data) / SESSION_ADDR), "address": address})
    running = nu.With(
        nu.Provide(Wiped, {"dirs": [uploads]}),
        recorded,
        body=nu.Race(served, *beside) if beside else served,
    )
    return opening(
        root,
        throwaway=throwaway,
        locks=[(WEB_LOCK, "web")],
        log=(WEB_LOG, "web"),
        blobs=blobs,
        body=running,
    )
