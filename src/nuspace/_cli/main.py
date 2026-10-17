"""Root click group for the ``nuspace`` command, rendered by rich-click.

One module per command under :mod:`.commands`, attached here.
"""

from __future__ import annotations

import rich_click as click

from nuspace._branding import BLUE, PURPLE, TAGLINE

from ._meta import version_of
from .commands.init import init
from .commands.run import run
from .commands.telemetry import telemetry
from .commands.verse import verse


__all__ = ["cli", "main"]


# The brand duo: purple headers, blue values.
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
    help=f"nuspace: {TAGLINE}.",
)
@click.version_option(
    version_of("nuspace"),
    "-V",
    "--version",
    prog_name="nuspace",
    message=(
        f"nuspace {version_of('nuspace')} · nucore {version_of('nucore')}"
        f" · nustd {version_of('nustd')}"
    ),
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Root ``nuspace`` group. Help when no command is given."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


cli.add_command(init)
cli.add_command(run)
cli.add_command(verse)
cli.add_command(telemetry)


def main() -> None:
    """Console script entry point."""
    cli()
