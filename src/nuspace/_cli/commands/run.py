"""``nuspace run``: run a space, its infra, kernel and web, or one of them alone.

A space runs in three layers, each assuming the ones under it: infra
(what it runs on), the kernel, and web. The space's assembly
(:func:`~nuspace._cli._meta.assembly`, ``local`` for a new space) does the
work, through its entry points:

- by default its ``run``: infra in this process, the kernel and web each
  in a process of its own, web started again if it dies.
- ``--headless``: its ``infra`` and ``kernel``, in this process, no web.
- ``--infra``, ``--kernel``, ``--web``: that one component alone, in this
  process, beside the others run in other shells, started in that order.
  Each refuses to start without what it needs running.

Plain and headless, a space whose assembly's ``init`` has not run is
initialized first, made if missing: its ``meta.json`` read as the command
starts (:func:`~nuspace._cli._meta.initialized`), the init a step before
the run in the same term. The single component flags never
init: they refuse a space not initialized (``nuspace init`` does it).

Runs until interrupted, then the kernel ends what it started and the
brackets stop the workers. Which space is
:func:`~nuspace._cli._meta.space_root`: PATH, else the nearest space up
from here, else home. ``--tmp`` is a throwaway one, made and initialized
here, gone at close: a ``nustd.fs.tmp`` dir whose path the
assembly's entry points run on, its init first. Only plain and headless
take it, since nothing another shell runs could find it. The header names
the space's root either way.

``--with`` names a Plane an installed package adds, ``pkg.plane`` as
``nuspace verse`` lists them, or a bare name for a nuverse Plane: web
makes it in the space once and the tab opens on it. Headless or with
``--kernel``, the kernel makes it beside its driver; infra alone takes no
plane. The next run with the same name reopens the newest plane made from
it, unless removed. The header names the Plane: its id is only known once
the space is open. A space whose component runs already, or of an older
store format, is refused with a short error.

The port, where web runs: ``--port`` binds that one and a taken one is a
short error. Without it, the first free port from 8080 up.
"""

from __future__ import annotations

import errno
import socket
from typing import TYPE_CHECKING

import rich_click as click

import nustd.fs
from nuspace.errors import Refused
from nuspace.space.local.drivers import opened_on
from nuspace.specs import registered_name

from .._installed import resolve
from .._meta import (
    EXIT,
    announce,
    assembly,
    hold,
    initialized,
    path_argument,
    space_root,
    tmp_option,
)


if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    import nu


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


#: The tag the command line mounts a throwaway space's temp dir under.
TMP = nustd.fs.FsRef("nuspace.cli.tmp")


def throwaway_on(space: ModuleType, on: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """``on(root)`` on a throwaway root, initialized by ``space`` first: a ``nustd.fs.tmp`` dir, gone at close.

    The entry points take the ``nu.Attr`` the tmp lambda hands over the
    dir's path as their root, so one term makes the root, inits it, runs on
    it and removes it, and the workers ``run`` teleports to read it too.
    """
    return nustd.fs.tmp(tag=TMP, prefix="nuspace-", body=lambda root: space.init(root) >> on(root))


#: The flags that run one component alone, by the name of the entry point.
ALONE = ("infra", "kernel", "web")


def _alone(headless: bool, tmp: bool, plane: str | None, **flags: bool) -> str | None:
    """The one component asked to run alone, or None. Two, or one with ``--headless`` or ``--tmp``, is a usage error."""
    given = [name for name in ALONE if flags[name]]
    if len(given) > 1:
        raise click.UsageError("Give one of --infra, --kernel or --web, not more.")
    if not given:
        return None
    (one,) = given
    if headless:
        raise click.UsageError(f"Give --headless or --{one}, not both.")
    if tmp:
        msg = f"--tmp with --{one}: nothing another shell runs could find a throwaway space."
        raise click.UsageError(msg)
    if plane is not None and one == "infra":
        raise click.UsageError("--with makes a plane, which infra alone does not run.")
    return one


@click.command(
    short_help="Run a space: infra, its kernel and web, or one of them.",
    help=(
        "Run the space at PATH: infra here, its kernel and its web each in a process of its"
        " own, web started again if it stops. --headless runs infra and the kernel, no web."
        " Both initialize the space first if it is not, made if missing. --infra, --kernel"
        " or --web runs that one alone, never initializes, and refuses to start without what"
        " it needs: infra for the kernel, the kernel for web. Without PATH, the nearest"
        " space up from here, else the home space at ~."
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
        " Headless or with --kernel, the kernel makes it."
    ),
)
@click.option(
    "--headless",
    is_flag=True,
    help="Infra and the kernel, no web. Initializes the space first, like a plain run.",
)
@click.option(
    "--infra",
    "infra_only",
    is_flag=True,
    help="Infra alone, what the space runs on. Start it first, then --kernel, then --web.",
)
@click.option(
    "--kernel",
    "kernel_only",
    is_flag=True,
    help="The kernel alone: refused without infra running (--infra in another shell).",
)
@click.option(
    "--web",
    "web_only",
    is_flag=True,
    help="The web alone: refused without a kernel running (--kernel in another shell).",
)
@click.option(
    "--host", default="127.0.0.1", show_default=True, help="Interface web binds, where it runs."
)
@click.option(
    "-p",
    "--port",
    type=int,
    help="Port web binds, an error if taken. Default: the first free one from 8080.",
)
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab once web is up.")
def run(
    path: str | None,
    tmp: bool,
    plane: str | None,
    headless: bool,
    infra_only: bool,
    kernel_only: bool,
    web_only: bool,
    host: str,
    port: int | None,
    no_browser: bool,
) -> None:
    """Run until Ctrl+C."""
    alone = _alone(headless, tmp, plane, infra=infra_only, kernel=kernel_only, web=web_only)
    path = space_root(path, tmp=tmp)
    space = assembly(path)
    serves = alone == "web" or (alone is None and not headless)
    if serves:
        port = _port(host, port)
    try:
        spec = None
        made = None
        if plane is not None:
            spec = resolve(plane)
            made = registered_name(spec)
        served = {"host": host, "port": port, "open_browser": not no_browser}
        body = None if spec is None else opened_on(spec)

        def on(root: str | nu.Nu) -> nu.Nu:
            if alone == "infra":
                return space.infra(root)
            if alone == "kernel":
                return space.kernel(root, body=body)
            if alone == "web":
                return space.web(root, plane=spec, **served)
            if headless:
                return space.infra(root, body=space.kernel(root, body=body))
            return space.run(root, into=EXIT, plane=spec, **served)

        if path is None:
            term = throwaway_on(space, on)
        elif alone is None and not initialized(path):
            # Plain and headless init first, a step of the same term: made if missing.
            term = space.init(path) >> on(path)
        else:
            term = on(path)
    except Refused as e:
        raise click.ClickException(str(e)) from None
    quiet = None if serves else f"{alone} alone" if alone else "headless"
    announce(path, alone=quiet, plane=made)
    code = hold(term)
    if code:
        raise SystemExit(code)
