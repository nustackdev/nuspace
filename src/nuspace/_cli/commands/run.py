"""``nuspace run``: run a space, its kernel and web as two processes, or one of them alone.

The space's assembly (:func:`~nuspace._cli._meta.assembly`, ``local`` for
a new space) does the work, through its entry points:

- by default its ``run``: the kernel and web, each in a process of its
  own, web started again if it dies.
- ``--headless``: its ``infra`` and ``kernel``, in this process, no web.
- ``--web``: its ``web`` alone, in this process, beside a kernel run
  elsewhere (``--headless`` in another shell) or none yet: what web asks
  for waits until a kernel runs.

Runs until interrupted, then the kernel ends what it started and the
brackets stop the workers. Which space is
:func:`~nuspace._cli._meta.space_root`: PATH, made a space if it is not
one, else the nearest space up from here, else home. ``--tmp`` is a
throwaway one, gone at close. The header names the space's root either way.

``--with`` names a Plane an installed package adds, ``pkg.plane`` as
``nuspace verse`` lists them, or a bare name for a nuverse Plane: web
makes it in the space once and the tab opens on it. Headless, the kernel
makes it beside its driver. The next run with the same name reopens the
newest plane made from it, unless removed. The header names the Plane:
its id is only known once the space is open. A space whose kernel (or
web) runs already, or of an older store format, is refused with a short
error.

The port: ``--port`` binds that one and a taken one is a short error.
Without it, the first free port from 8080 up.
"""

from __future__ import annotations

import errno
import socket

import rich_click as click

import nu
from nuspace.errors import Refused
from nuspace.space.local.plane import plane_of
from nuspace.specs import registered_name

from .._installed import resolve
from .._meta import announce, assembly, hold, path_argument, space_root, tmp_option


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
    short_help="Run a space: its kernel and web, or one of them.",
    help=(
        "Run the space at PATH, made if missing: its kernel and its web, each in a process"
        " of its own, web started again if it stops. --headless runs the kernel alone,"
        " --web the web alone. Without PATH, the nearest space up from here, else the"
        " home space at ~."
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
    "--headless",
    is_flag=True,
    help="The kernel alone, no web. --host, --port and --no-browser go unused.",
)
@click.option(
    "--web",
    "web_only",
    is_flag=True,
    help="The web alone, no kernel: run one with --headless in another shell.",
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
    web_only: bool,
    host: str,
    port: int | None,
    no_browser: bool,
) -> None:
    """Run until Ctrl+C."""
    if headless and web_only:
        raise click.UsageError("Give --headless or --web, not both.")
    path = space_root(path, tmp=tmp)
    space = assembly(path)
    if not headless:
        port = _port(host, port)
    made = None
    try:
        spec = None
        if plane is not None:
            spec = resolve(plane)
            made = registered_name(spec)
        served = {"host": host, "port": port, "open_browser": not no_browser}
        if headless:
            body = None if spec is None else nu.let("", lambda p: plane_of(spec, p)) >> nu.Park()
            term = space.infra(path, body=space.kernel(path, body=body))
        elif web_only:
            term = space.web(path, plane=spec, **served)
        else:
            term = space.run(path, plane=spec, **served)
    except Refused as e:
        raise click.ClickException(str(e)) from None
    announce(path, headless=headless, plane=made)
    code = hold(term)
    if code:
        raise SystemExit(code)
