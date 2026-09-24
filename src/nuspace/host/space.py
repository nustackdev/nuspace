"""open_space: the whole system in one term, as a host runs it.

Layer three. It composes, nothing more: the registry, the kernel's
brackets, the services, and the web device when asked for. The order, all
inside :func:`~nuspace.system.kernel.open_kernel` after reconcile:

1. :func:`~nuspace.system.services.ensure_system`: the service planes, made
   where missing;
2. :func:`~nuspace.system.home.ensure_home`: the home plane, made where
   missing, so it exists before the web device serves ``/``;
3. :func:`~nuspace.system.home.write_info`: ``Space.state.info`` for this
   open (store path, when, versions);
4. :func:`~nuspace.system.services.nav.clear_connections`: tabs of a previous
   run dropped, so nav never brings a plane up for one (D34);
5. init started by the kernel's own :func:`~nuspace.system.kernel.init_start`,
   which brings up its boot list (nav, supervisor, reload by default);
6. the web device and ``body``, beside the kernel.

The kernel's ``init=`` would start init beside the body, before the service
planes are sure to exist on a first open, so the start is sequenced here
instead (the same term, same ``by``).

Workers import :mod:`nuspace`, and so this module: the web device, which
pulls in the web server, is imported only when a space serves.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import nu
from nuspace.system.home import ensure_home, write_info
from nuspace.system.kernel import DEFAULT_SPARES, init_start, open_kernel
from nuspace.system.services import ensure_system
from nuspace.system.services import init as init_service
from nuspace.system.services.nav import clear_connections
from nuspace.system.utils import park

from .registry import Extension, Registry, RegistryWarning


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from nuspace.ops import App, Snippet
    from nuspace.system.kernel import EnvFactory


__all__ = ["open_space", "space_registry"]


def space_registry(
    *,
    apps: Sequence[App] = (),
    snippets: Sequence[Snippet] = (),
    envs: Mapping[str, EnvFactory] | None = None,
    extensions: Sequence[Extension] | None = None,
    discover: bool = True,
) -> Registry:
    """What a space registers: the loose arguments, then ``extensions``, then installed ones.

    Args:
        apps: apps passed directly, ahead of everything.
        snippets: snippets passed directly.
        envs: env factories passed directly.
        extensions: explicit extensions, after the loose arguments.
        discover: also load the ``nuspace.extensions`` entry points.
    """
    loose = Extension(tuple(apps), tuple(snippets), dict(envs or {}), name="open_space")
    return Registry.build([loose, *(extensions or ())], discovered=None if discover else [])


def _with_session(envs: Mapping[str, EnvFactory], web: Mapping[str, EnvFactory]) -> dict:
    """The registry's envs, with the web device's on top: it owns what it serves."""
    merged = dict(envs)
    for name, factory in web.items():
        if name in merged:
            warnings.warn(
                f"env {name!r} is the web device's, the registered one is ignored",
                RegistryWarning,
                stacklevel=3,
            )
        merged[name] = factory
    return merged


def open_space(
    path: str | None = None,
    *,
    web: bool = True,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    static: str | None = "nuspace_ui",
    spares: int = DEFAULT_SPARES,
    apps: Sequence[App] = (),
    snippets: Sequence[Snippet] = (),
    envs: Mapping[str, EnvFactory] | None = None,
    space_envs: Sequence[Sequence[str] | str] = (),
    extensions: Sequence[Extension] | None = None,
    discover: bool = True,
    body: nu.Nu | None = None,
    name: str | None = None,
) -> nu.Nu:
    """A space, opened: kernel, services, and the browser shell when ``web``.

    Runs until ``body`` returns, or forever without one. Evaluate it under a
    ``if __name__ == "__main__"`` guard: workers are spawned and re-import
    the main module.

    Args:
        path: the store directory. None is a throwaway one, gone at close.
        web: serve the browser shell. False is headless: kernel and services.
        host: the interface the web server binds.
        port: the port the web server binds.
        open_browser: open a tab once the server is up.
        static: the wheel shipping the browser bundle. None serves the
            socket alone, eg for a vite dev server.
        spares: idle workers to keep up.
        apps: apps registered directly, ahead of any extension.
        snippets: snippets registered directly.
        envs: env factories registered directly.
        space_envs: env specs every run executes inside, outermost.
        extensions: extensions registered explicitly, ahead of discovered ones.
        discover: also register the extensions installed under the
            ``nuspace.extensions`` entry point group.
        body: host Nu run beside everything. The space closes when it returns.
        name: process name prefix for workers.
    """
    reg = space_registry(
        apps=apps, snippets=snippets, envs=envs, extensions=extensions, discover=discover
    )
    factories = dict(reg.envs)
    arms: list[nu.Nu] = []
    if web:
        from nuspace.system.devices.web.device import serve_web

        served, web_envs = serve_web(
            apps=list(reg.apps.values()),
            snippets=list(reg.snippets.values()),
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
        ensure_system()
        >> ensure_home()
        >> write_info(path)
        >> clear_connections()
        >> init_start(init_service.PLANE)
        >> beside,
        path=path,
        spares=spares,
        envs=factories,
        space_envs=space_envs,
        **kwargs,
    )
