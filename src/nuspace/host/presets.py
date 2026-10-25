"""Presets: the named ways to open a space, each one :func:`open_space` call.

- :func:`serve`: the browser shell, a tab opened on the way up.
- :func:`headless`: kernel and services, nothing drawn.
- :func:`with_plane`: either of those with one registered Plane made in
  the space, the tab opened on it.

The command line maps one command or flag to one preset and adds nothing of
its own. Anything else :func:`open_space` takes passes through.
"""

from __future__ import annotations

import asyncio
import webbrowser
from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.system.utils import park, snap

from .space import open_space


if TYPE_CHECKING:
    from nu.lang.runtime import Context
    from nuspace.ext import PlaneSpec


__all__ = ["headless", "plane_id", "serve", "with_plane"]


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


def plane_id(spec: PlaneSpec) -> str:
    """The plane id :func:`with_plane` makes ``spec`` under: fixed, so a second open finds it.

    Its name with the dot a dash, ``nudemos.movies`` as ``nudemos-movies``.
    """
    return spec.name.replace(".", "-")


class Browse:
    """Opens ``url`` in a browser once ``host:port`` takes a connection. Binds nothing anyone reads.

    For a body that runs beside the web device, which may not be up yet.
    Async only: a space is always run in a loop. Gives up quietly after
    ``timeout`` seconds.
    """

    def __init__(self, url: str, host: str, port: int, timeout: float = 30.0) -> None:
        self.url = url
        # A wildcard bind is reached on loopback.
        self.host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host  # noqa: S104
        self.port = port
        self.timeout = timeout

    async def asetup(self, ctx: Context) -> None:
        """Wait for the server to take a connection, then open the tab."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout
        while True:
            try:
                _, writer = await asyncio.open_connection(self.host, self.port)
            except OSError:
                if loop.time() > deadline:
                    return
                await asyncio.sleep(0.1)
                continue
            writer.close()
            break
        webbrowser.open(self.url)


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

    The plane goes in under :func:`plane_id`, made only where missing, so a
    plane opened again in the same space keeps what was done to it. Served,
    the tab opens on the plane rather than on home.
    """
    plane = plane_id(spec)
    made = nu.IfDo(snap(ops.plane_exists(plane)), nu.Noop(), ops.create_plane(spec, plane_id=plane))
    held = park()
    if not web:
        return open_space(path, web=False, body=made >> held, **kwargs)
    if open_browser:
        url = f"http://{host}:{port}/{plane}"
        held = nu.With(nu.Provide(Browse, {"url": url, "host": host, "port": port}), body=held)
    return open_space(
        path, web=True, host=host, port=port, open_browser=False, body=made >> held, **kwargs
    )
