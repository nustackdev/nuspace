"""Root click group for the ``nuspace`` command.

One option belongs to every command, which is which Space it means, so it sits
on the group and the commands read it off the click Context.

The commands mirror :mod:`nuspace.ops` and :mod:`nuspace.exec`: ``plane`` and
``cell`` write, ``run`` runs what was written. Nothing here reaches around ops
to the store.
"""

from __future__ import annotations

import rich_click as click

from nu._config.branding import BLUE, PURPLE
from nuspace.cli.cell import cell
from nuspace.cli.plane import plane
from nuspace.cli.space import clear, ls, run
from nuspace.cli.utils import DEFAULT_STORE, STORE_ENV, nuspace_version


__all__ = ["cli", "main"]


click.rich_click.USE_RICH_MARKUP = True
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


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="nuspace: a Space of Planes of Cells, and the runtime that runs them.",
)
@click.version_option(nuspace_version(), "-V", "--version", prog_name="nuspace")
@click.option(
    "-s",
    "--store",
    "path",
    envvar=STORE_ENV,
    default=DEFAULT_STORE,
    show_default=True,
    help=f"The Space to work on, a directory. Read from ${STORE_ENV} when set.",
)
@click.pass_context
def cli(ctx: click.Context, path: str) -> None:
    """Root ``nuspace`` group. Hands the store path down to every command."""
    ctx.obj = path
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli.add_command(run)
cli.add_command(ls)
cli.add_command(clear)
cli.add_command(plane)
cli.add_command(cell)


def main() -> None:
    """Console script entry point."""
    cli()
