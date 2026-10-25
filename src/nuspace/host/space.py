"""open_space: the whole system in one term, as a host runs it. init_space: one made.

Layer three. It composes, nothing more: the registry (:mod:`nuspace.ext`), the kernel's
brackets (the space directory's store and notification server, the pool),
the services, and the web device when asked for. The order, all
inside :func:`~nuspace.system.kernel.open_kernel` after reconcile:

1. :func:`~nuspace.system.services.ensure_system`: the service planes, made
   where missing;
2. :func:`~nuspace.system.home.ensure_home`,
   :func:`~nuspace.system.settings.ensure_settings` and
   :func:`~nuspace.system.search.ensure_search`: the home, settings and
   search planes, made where missing, so they exist before the web device
   serves;
3. :func:`~nuspace.system.home.write_info`: ``Space.state.info`` for this
   open (space path, when, versions);
4. :func:`~nuspace.system.services.nav.clear_connections`: tabs of a previous
   run dropped, so nav never brings a plane up for one (D34);
5. init started by the kernel's own :func:`~nuspace.system.kernel.init_start`,
   which brings up its boot list (nav, supervisor, reload, reactions by default);
6. the web device and ``body``, beside the kernel.

The kernel's ``init=`` would start init beside the body, before the service
planes are sure to exist on a first open, so the start is sequenced here
instead (the same term, same ``by``).

:func:`init_space` is steps 1 and 2 alone, in the store's brackets only: the
space directory made and seeded, and closed again, nothing run.

Workers import :mod:`nuspace`, and so this module: the web device, which
pulls in the web server, is imported only when a space serves.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import nu
from nuspace.ext import RegistryWarning, space_registry
from nuspace.system.home import ensure_home, write_info
from nuspace.system.kernel import DEFAULT_SPARES, init_start, open_kernel, store
from nuspace.system.search import ensure_search
from nuspace.system.services import ensure_system
from nuspace.system.services import init as init_service
from nuspace.system.services.nav import clear_connections
from nuspace.system.settings import ensure_settings
from nuspace.system.utils import park


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from nuspace.system.backends import Backend
    from nuspace.system.kernel import EnvFactory


__all__ = ["init_space", "open_space", "seed_space"]


def _with_session(envs: Mapping[str, EnvFactory], web: Mapping[str, EnvFactory]) -> dict:
    """The registry's envs, with the web device's on top: it owns what it serves."""
    merged = dict(envs)
    for name, factory in web.items():
        if name in merged:
            warnings.warn(
                f"Env {name!r} is the web device's, the registered one is ignored",
                RegistryWarning,
                stacklevel=3,
            )
        merged[name] = factory
    return merged


def seed_space() -> nu.Nu:
    """The planes every space holds before anything runs: services, home, settings, search.

    Each made where missing, so it is safe on every open.
    """
    return ensure_system() >> ensure_home() >> ensure_settings() >> ensure_search()


def init_space(path: str) -> nu.With:
    """The space at ``path`` made and seeded (:func:`seed_space`), then closed. Nothing runs.

    The store's brackets alone: no pool, no kernel, no web device. A space
    already there is left as it is, but for a system plane gone missing.

    Raises:
        NotASpace: ``path`` holds something other than a space.
    """
    return nu.With(store(path), body=seed_space())


def open_space(
    path: str | None = None,
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
    body: nu.Nu | None = None,
    name: str | None = None,
) -> nu.Nu:
    """A space, opened: kernel, services, and the browser shell when ``web``.

    Runs until ``body`` returns, or forever without one. Evaluate it under a
    ``if __name__ == "__main__"`` guard: workers are spawned and re-import
    the main module.

    Args:
        path: The space directory, created if missing: ``kernel.sqlite``
            (structure and runs), ``state.sqlite`` (program state) and the
            notification server's ``valkey/``. None is a throwaway one,
            gone at close.
        web: Serve the browser shell. False is headless: kernel and services.
        host: The interface the web server binds.
        port: The port the web server binds.
        open_browser: Open a tab once the server is up.
        static: The wheel shipping the browser bundle. None serves the
            socket alone, eg for a vite dev server.
        spares: Idle workers to keep up.
        extensions: The installed packages whose extensions register, by
            entry point name. None registers every installed one, ``()``
            none. Planes, Cells and content kinds register only so, by
            package, so a worker finds each by name.
        envs: Env factories of the host's own, ahead of every package's.
        space_envs: Env specs every run executes inside, outermost.
        backends: Backend classes by name, on top of the built in ``async``
            and ``mp``. A plane runs on the one its ``backend`` prop names.
        body: Host Nu run beside everything. The space closes when it returns.
        name: Process name prefix for workers.
    """
    reg = space_registry(extensions=extensions, envs=envs)
    factories = dict(reg.envs)
    arms: list[nu.Nu] = []
    if web:
        from nuspace.system.devices.web.device import serve_web

        served, web_envs = serve_web(
            registry=reg,
            host=host,
            port=port,
            static=static,
            open_browser=open_browser,
        )
        factories = _with_session(factories, web_envs)
        arms.append(served)
    arms.append(park() if body is None else body)
    beside = arms[0] if len(arms) == 1 else nu.Race(*arms)
    kwargs = {} if name is None else {"name": name}
    return open_kernel(
        seed_space()
        >> write_info(path)
        >> clear_connections()
        >> init_start(init_service.PLANE)
        >> beside,
        path=path,
        spares=spares,
        envs=factories,
        space_envs=space_envs,
        backends=backends,
        **kwargs,
    )
