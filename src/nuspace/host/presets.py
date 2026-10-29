"""Presets: the named ways to open a space, each one :func:`open_space` call.

- :func:`serve`: the browser shell, a tab opened on the way up.
- :func:`headless`: kernel and services, nothing drawn.
- :func:`with_plane`: either of those with one registered Plane made in
  the space, the tab opened on it. The space records which plane it made
  for that Plane, so the next open with it reopens the same one.

The command line maps one command or flag to one preset and adds nothing of
its own. Anything else :func:`open_space` takes passes through.
"""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Command, Ref
from nuspace import ops
from nuspace.ext.registry import registered_name
from nuspace.ops.utils import atomic
from nuspace.shapes import Space
from nuspace.system.utils import park, snap

from .space import open_space


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime
    from nuspace.ext import PlaneSpec


__all__ = ["Browse", "BrowserRef", "browse", "headless", "serve", "with_plane"]


def serve(
    path: str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    **kwargs: object,
) -> nu.Nu:
    """The space at ``path``, served in a browser on ``host:port``."""
    return open_space(path, web=True, host=host, port=port, open_browser=open_browser, **kwargs)


def headless(path: str | None = None, **kwargs: object) -> nu.Nu:
    """The space at ``path`` with kernel and services only, no web device."""
    return open_space(path, web=False, **kwargs)


async def browse(url: str, host: str, port: int, timeout: float = 30.0) -> None:
    """Open ``url`` in a browser once ``host:port`` takes a connection.

    For a body that runs beside the web device, which may not be up yet.
    Gives up quietly after ``timeout`` seconds.
    """
    # A wildcard bind is reached on loopback.
    host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host  # noqa: S104
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        try:
            _, writer = await asyncio.open_connection(host, port)
        except OSError:
            if loop.time() > deadline:
                return
            await asyncio.sleep(0.1)
            continue
        writer.close()
        break
    webbrowser.open(url)


class BrowserRef(Ref):
    """The Ref naming the browser, what :class:`Browse` writes. Nothing is bound.

    Like :class:`~nuspace.ops.usage.TelemetryRef`: declared so the engine
    keeps the open ordered and never folds it away as a pure read.

    Yields:
        None.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        return lambda rt: None

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> None:
            return None

        return athunk


class Browse(Command):
    """:func:`browse` as a term: the url read at run time, ``host:port`` fixed at build.

    Async only: a space is always run in a loop.

    Args:
        url: What to open, a str term.
        host: Where the server binds.
        port: The port it binds.
        timeout: Seconds to wait for it before giving up quietly.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, url: nu.StrArg, host: str, port: int, timeout: float = 30.0) -> None:
        super().__init__(BrowserRef(), url)
        self._payload = dict(self._payload)
        self._payload.update(host=host, port=port, timeout=timeout)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            msg = "Browse runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        _, url = children
        p = self._payload

        async def athunk(rt: Runtime) -> None:
            await browse(str(await url(rt)), p["host"], p["port"], p["timeout"])

        return athunk


def with_plane(
    spec: PlaneSpec,
    path: str | None = None,
    *,
    web: bool = True,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    **kwargs: object,
) -> nu.Nu:
    """The space at ``path`` with ``spec`` made in it once, served on ``host:port`` or headless.

    The plane gets a minted id like any other, and the space keeps it under
    ``spec``'s registered name in ``Space.state.made``. A later open with
    the same ``spec`` finds the plane there and keeps what was done to it.
    A plane that is gone (removed, or never recorded) is made afresh and
    the record points at the new one. Served, the tab opens on the plane
    rather than on home.
    """
    made = Space.state.made
    name = registered_name(spec)

    def opened(plane: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(plane)
        make = ops.create_plane(spec, into=plane) >> atomic(made.set_item(name, pid))
        steps = [
            plane.set(snap(made.get_item(name, ""))),
            nu.IfDo(snap(ops.plane_exists(pid)), nu.Noop(), make),
        ]
        if web and open_browser:
            steps.append(Browse(nu.Str(f"http://{host}:{port}/") + pid, host, port))
        return nu.Sequential(*steps, park())

    body = nu.let("", opened)
    if not web:
        return open_space(path, web=False, body=body, **kwargs)
    return open_space(path, web=True, host=host, port=port, open_browser=False, body=body, **kwargs)
