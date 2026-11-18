"""``nuspace run``: open a space, served in a browser or headless.

One flag, one :mod:`nuspace.space.local` preset: :func:`~nuspace.space.local.serve` by
default, :func:`~nuspace.space.local.headless` with ``--headless``. Runs until
interrupted, then the host ends what is live and the brackets stop the
workers. Which space is :func:`~nuspace._cli._meta.space_root`: PATH, made
a space if it is not one, else the nearest space up from here, else home.
``--tmp`` is a throwaway one, gone at close. The header names the space's root either way.

``--with`` names a Plane an installed package adds, ``pkg.plane`` as
``nuspace verse`` lists them, or a bare name for a nuverse Plane: it is made
in the space once, through :func:`~nuspace.space.local.with_plane`, and the tab
opens on it. The next run with the same name reopens the newest plane made
from it, unless removed. The header names the Plane: its id is only known
once the space is open. A space open in another host, or of an older store
format, is refused with a short error.

The port: ``--port`` binds that one and a taken one is a short error.
Without it, the first free port from 8080 up.
"""

from __future__ import annotations

import errno
import socket

import rich_click as click

from nuspace.errors import Refused
from nuspace.space.local import presets
from nuspace.specs import registered_name

from .._installed import resolve
from .._meta import announce, hold, path_argument, space_root, tmp_option


__all__ = ["run"]


#: Where the search for a free port starts when none is given, and how far it goes.
DEFAULT_PORT = 8080
_SCAN = 100


def _bindable(host: str, port: int) -> bool:
    """Whether the server could bind ``host:port`` now, probed as uvicorn binds it."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE)
    except socket.gaierror as e:
        raise click.ClickException(f"Cannot bind {host}: {e.strerror}.") from None
    family, kind, proto, _, address = infos[0]
    with socket.socket(family, kind, proto) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(address)
        except OSError as e:
            if e.errno in (errno.EADDRINUSE, errno.EACCES):
                return False
            raise click.ClickException(f"Cannot bind {host}:{port}: {e.strerror}.") from None
    return True


def _port(host: str, port: int | None) -> int:
    """The port to serve on: ``port`` if free, else a short error; None, the first free from 8080."""
    if port is not None:
        if not _bindable(host, port):
            raise click.ClickException(
                f"Port {port} on {host} is taken. Pick another with -p, or drop -p for a free one."
            )
        return port
    for candidate in range(DEFAULT_PORT, DEFAULT_PORT + _SCAN):
        if _bindable(host, candidate):
            return candidate
    raise click.ClickException(
        f"No free port on {host} in {DEFAULT_PORT}-{DEFAULT_PORT + _SCAN - 1}. Pick one with -p."
    )


@click.command(
    short_help="Open a space, in a browser or headless.",
    help=(
        "Open the space at PATH, made if missing, and serve it in a browser, or headless:"
        " kernel and services, nothing drawn. Without PATH, the nearest space up from"
        " here, else the home space at ~."
    ),
)
@path_argument
@tmp_option
@click.option(
    "--with",
    "plane",
    metavar="PLANE",
    help=(
        "Make this plane in the space once and open on it: pkg.plane, as nuspace verse"
        " lists them, or a bare name for a nuverse plane (jobs is nuverse.jobs)."
    ),
)
@click.option(
    "--headless", is_flag=True, help="Serve no browser. --host, --port and --no-browser go unused."
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option(
    "-p",
    "--port",
    type=int,
    help="Port to bind, an error if taken. Default: the first free one from 8080.",
)
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab on the way up.")
def run(
    path: str | None,
    tmp: bool,
    plane: str | None,
    headless: bool,
    host: str,
    port: int | None,
    no_browser: bool,
) -> None:
    """Run until Ctrl+C."""
    path = space_root(path, tmp=tmp)
    if not headless:
        port = _port(host, port)
    web = {"host": host, "port": port, "open_browser": not no_browser}
    made = None
    try:
        if plane is not None:
            spec = resolve(plane)
            made = registered_name(spec)
            if headless:
                term = presets.with_plane(path, spec, web=False)
            else:
                term = presets.with_plane(path, spec, **web)
        elif headless:
            term = presets.headless(path)
        else:
            term = presets.serve(path, **web)
    except Refused as e:
        raise click.ClickException(str(e)) from None
    announce(path, headless=headless, plane=made)
    hold(term)
