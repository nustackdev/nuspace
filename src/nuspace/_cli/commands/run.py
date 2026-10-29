"""``nuspace run``: open a space, served in a browser or headless.

One flag, one :mod:`nuspace.host` preset: :func:`~nuspace.host.serve` by
default, :func:`~nuspace.host.headless` with ``--headless``. Runs until
interrupted, then the brackets reap the workers on the way out. PATH is the
space directory, made if missing. With no path the space is a throwaway
directory, gone at close.

``--with`` names a Plane an installed package adds, ``pkg.plane`` as
``nuspace verse`` lists them, or a bare name for a nuverse Plane: it is made
in the space once, through :func:`~nuspace.host.with_plane`, and the tab
opens on it. The space remembers the plane it made, so the next run with
the same name reopens it. The header names the Plane: its id is only known
once the space is open.
"""

from __future__ import annotations

import rich_click as click

from nuspace.ext.registry import registered_name
from nuspace.host import presets

from .._installed import resolve
from .._meta import STORE_ENV, announce, hold, opened, path_argument


__all__ = ["run"]


@click.command(
    short_help="Open a space, in a browser or headless.",
    help=(
        "Open the space at PATH and serve it in a browser, or headless: kernel and"
        f" services, nothing drawn. PATH from ${STORE_ENV}, a throwaway space without one."
    ),
)
@path_argument
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
    "--headless", is_flag=True, help="No web device. --host, --port and --no-browser go unused."
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("-p", "--port", default=8080, show_default=True, help="Port to bind.")
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab on the way up.")
def run(
    path: str | None, plane: str | None, headless: bool, host: str, port: int, no_browser: bool
) -> None:
    """Run until Ctrl+C."""
    web = {"host": host, "port": port, "open_browser": not no_browser}
    if plane is not None:
        spec = resolve(plane)
        made = registered_name(spec)
        if headless:
            term = opened(presets.with_plane, spec, path, web=False)
        else:
            term = opened(presets.with_plane, spec, path, **web)
    elif headless:
        term = opened(presets.headless, path)
        made = None
    else:
        term = opened(presets.serve, path, **web)
        made = None
    announce(path, headless=headless, plane=made)
    hold(term)
