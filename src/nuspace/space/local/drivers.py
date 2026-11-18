"""local.kernel and local.web: one driver each, in the process that runs the term.

Both open the space the same way (:mod:`.opening`), each under its own
lock, so one kernel and one web run on a space, in one process or two.
Neither makes or inits a space: each refuses one whose init has not run
(``local.init``), except a throwaway root, which it makes and inits first.
The kernel owns the notification server and web joins it, so web starts
only beside a running kernel: it waits a moment for one coming up, else
it is refused. A kernel stopped under a live web takes the server with
it; web's tabs hear again once a kernel is back. They meet only through
the stores, the notifier and two files
of local's: ``devices/web/session.addr``, where web's tab sessions answer
(:mod:`.session`), and the uploads dir, both named by :mod:`.layout`.

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

import functools
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
from ..blocks.lock import held
from ..blocks.meta import data_dir, resolve_root
from ..blocks.notifier import answers
from ..blocks.required import Required
from ..blocks.workers import DEFAULT_NAME, DEFAULT_SPARES, worker_pool
from . import binding
from .disk import Wiped
from .layout import KERNEL_LOCK, KERNEL_LOG, SESSION_ADDR, UPLOADS_DIR, WEB_LOCK, WEB_LOG
from .opening import ROOTS, bracketed, fresh, path_set
from .plane import found, plane_of
from .session import Recorded, free_address, session_env


if TYPE_CHECKING:
    import os
    from collections.abc import Mapping, Sequence

    from nu.context.fabric import Provide
    from nuspace.kernel import Backend, EnvFactory
    from nuspace.specs import PlaneSpec


__all__ = ["kernel", "web"]


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
) -> nu.Nu:
    """The space's kernel in this process, run until ``body`` returns, or until cancelled without one.

    See the module for the order. At a clean close (cancelled, or ``body``
    returning) what the kernel started and left live is ended
    ``interrupted``. A space not initialized, of another store format,
    another assembly's, or one whose kernel runs elsewhere, is refused
    before anything is written. Logs to ``kernel/kernel.log``.

    Args:
        path: The space's root, initialized (``local.init``); its data in
            ``.nuspace/``. None is a throwaway one, made and initialized
            here, removed at close.
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
            assembly's space, or a kernel of this space running already.
    """
    root, throwaway = resolve_root(path)
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
    driven = bracketed(
        root,
        locks=[(KERNEL_LOCK, "kernel")],
        log=(KERNEL_LOG, "kernel"),
        notifier=binding.served(data),
        blobs=blobs,
        body=path_set(root) >> opened() >> running,
    )
    return fresh(root, throwaway, driven)


#: Seconds web waits for a kernel whose lock is held but whose server is not up yet.
KERNEL_WAIT = 30.0

#: Seconds web looks again at first for a kernel starting beside it, its lock not taken yet.
KERNEL_GRACE = 2.0


def kernels(data: str) -> nu.Provide:
    """The kernel's notification server answering, or web refused: no kernel, nothing to serve."""
    refusal = (
        "the kernel of this space is not running: start it first"
        " (nuspace run, or nuspace run --headless beside this)"
    )
    return nu.Provide(
        Required,
        {
            "check": functools.partial(answers, binding.valkey_dir(data)),
            "refusal": refusal,
            "wait": KERNEL_WAIT,
            "waiting": functools.partial(held, str(Path(data) / KERNEL_LOCK)),
            "grace": KERNEL_GRACE,
        },
    )


def opened_on(spec: PlaneSpec, host: str, port: int, browse: bool) -> nu.Nu:
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
) -> nu.Nu:
    """The space's web in this process, served until ``body`` returns, or until cancelled without one.

    See the module for the order. A kernel must run on the space: web joins
    its notification server, waiting up to :data:`KERNEL_WAIT` seconds for
    one coming up, and is refused when there is none. A space not
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
    beside = [] if plane is None else [opened_on(found(plane), host, port, open_browser)]
    if body is not None:
        beside.append(body)
    recorded = nu.Provide(Recorded, {"path": str(Path(data) / SESSION_ADDR), "address": address})
    running = nu.With(
        nu.Provide(Wiped, {"dirs": [uploads]}),
        recorded,
        body=nu.Race(served, *beside) if beside else served,
    )
    driven = bracketed(
        root,
        locks=[(WEB_LOCK, "web")],
        log=(WEB_LOG, "web"),
        notifier=kernels(data),
        blobs=blobs,
        body=running,
    )
    return fresh(root, throwaway, driven)
