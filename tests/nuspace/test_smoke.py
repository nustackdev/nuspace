from click.testing import CliRunner

from nuspace.cli import cli


def test_help():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "nuspace" in result.output


def test_version_flag():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
