"""Root click group for the ``nuspace`` CLI.

No commands yet. The CLI is a DX layer that will grow once the core
primitives settle. External automation should attach to a running space
via ``nu.proxy`` instead of via bespoke CLI commands.
"""

from __future__ import annotations

import rich_click as click

from nuspace.cli._meta import nuspace_version


click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.MAX_WIDTH = 100


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    help="nuspace: a Nu dialect.",
)
@click.version_option(nuspace_version(), "-V", "--version", prog_name="nuspace")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Root ``nuspace`` group. Commands land here as the DX layer grows."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def main() -> None:
    """Console-script entry point."""
    cli()
