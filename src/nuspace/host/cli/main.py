"""Root click group for the ``nuspace`` command, and its two commands.

``serve`` opens a space with the browser shell, ``run`` opens it headless.
Both run until interrupted, then the brackets reap the workers on the way
out. PATH is the space directory, made if missing. With no path the space
is a throwaway directory, gone at close.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import rich_click as click
from rich.console import Console
from rich.text import Text

import nu
from nu._config.branding import BLUE, PURPLE
from nuspace.host.space import open_space
from nuspace.system.kernel import NotASpace


__all__ = ["STORE_ENV", "cli", "main"]


#: The environment variable naming the space directory when no path is given.
STORE_ENV = "NUSPACE_STORE"

console = Console()

click.rich_click.STYLE_HEADER_TEXT = f"bold {PURPLE}"
click.rich_click.STYLE_USAGE = f"bold {PURPLE}"
click.rich_click.STYLE_SWITCH = f"bold {PURPLE}"
click.rich_click.STYLE_OPTION = f"bold {BLUE}"
click.rich_click.STYLE_COMMAND = f"bold {BLUE}"
click.rich_click.STYLE_METAVAR = BLUE
click.rich_click.STYLE_HELPTEXT_FIRST_LINE = "bold"
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 100


def nuspace_version() -> str:
    """The installed version, or a dev marker when nuspace is not installed."""
    try:
        return version("nuspace")
    except PackageNotFoundError:
        return "0.0.0+dev"


def _path_argument(fn: click.Command) -> click.Command:
    """The space directory every command takes, from the environment when absent."""
    return click.argument("path", required=False, envvar=STORE_ENV)(fn)


def _announce(path: str | None, how: str) -> None:
    """Say which space this is and how it is open."""
    where = path or "Throwaway space, gone at close"
    console.print(Text.assemble(("nuspace", f"bold {PURPLE}"), ("  ", ""), (where, "dim")))
    console.print(f"[dim]{how}, Ctrl+C to stop[/dim]")


def _opened(path: str | None, **kwargs: object) -> nu.Nu:
    """The space at ``path``, or a short error when ``path`` is not one."""
    try:
        return open_space(path, **kwargs)
    except NotASpace as e:
        raise click.ClickException(str(e)) from None


def _hold(term: nu.Nu) -> None:
    """Run a space until interrupted, then let the brackets reap the fleet."""
    try:
        nu.run_in_loop(term, nu.Context())
    except KeyboardInterrupt:
        console.print("[dim]Stopped[/dim]")


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="nuspace: a space of planes of cells, and the system that runs them.",
)
@click.version_option(nuspace_version(), "-V", "--version", prog_name="nuspace")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Root ``nuspace`` group. Help when no command is given."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command(help=f"Open the space at PATH and serve it in a browser. PATH from ${STORE_ENV}.")
@_path_argument
@click.option("--host", default="127.0.0.1", show_default=True, help="Interface to bind.")
@click.option("-p", "--port", default=8080, show_default=True, help="Port to bind.")
@click.option("--no-browser", is_flag=True, help="Do not open a browser tab on the way up.")
def serve(path: str | None, host: str, port: int, no_browser: bool) -> None:
    """Serve until Ctrl+C."""
    term = _opened(path, host=host, port=port, open_browser=not no_browser)
    _announce(path, f"http://{host}:{port}")
    _hold(term)


@cli.command(help=f"Open the space at PATH headless: kernel and services. PATH from ${STORE_ENV}.")
@_path_argument
def run(path: str | None) -> None:
    """Run until Ctrl+C."""
    term = _opened(path, web=False)
    _announce(path, "Headless")
    _hold(term)


def main() -> None:
    """Console script entry point."""
    cli()
