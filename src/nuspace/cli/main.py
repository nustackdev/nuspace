"""Root click group for the `nuspace` CLI (rendered via rich-click)."""

from __future__ import annotations

import sys

import rich_click as click

from nuspace.cli._meta import nuspace_version


click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 100


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="nuspace: self-hosted Nu runtime.",
)
@click.version_option(nuspace_version(), "-V", "--version", prog_name="nuspace")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Root `nuspace` group; individual commands are attached below."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
def run() -> None:
    """Start the nuspace runtime (not yet implemented)."""
    click.echo("nuspace: not implemented yet.")
    sys.exit(1)


def main() -> None:
    """Console-script entrypoint for `nuspace`."""
    cli()
