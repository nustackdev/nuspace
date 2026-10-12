"""``nuspace run``: open a space, served in a browser or headless.

One flag, one :mod:`nuspace.host` preset: :func:`~nuspace.host.serve` by
default, :func:`~nuspace.host.headless` with ``--headless``. Runs until
interrupted, then the brackets reap the workers on the way out. PATH is the
space directory, made if missing. With no path the space is a throwaway
directory, gone at close.
"""

from __future__ import annotations

import rich_click as click

from nuspace.host import presets

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
    "--headless", is_flag=True, help="No web device. --host, --port and --no-browser go unused."
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("-p", "--port", default=8080, show_default=True, help="Port to bind.")
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab on the way up.")
def run(path: str | None, headless: bool, host: str, port: int, no_browser: bool) -> None:
    """Run until Ctrl+C."""
    if headless:
        term = opened(presets.headless, path)
        announce(path, "Headless")
    else:
        term = opened(presets.serve, path, host=host, port=port, open_browser=not no_browser)
        announce(path, f"http://{host}:{port}")
    hold(term)
