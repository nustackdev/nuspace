"""The command line: help and version, each command wired to its preset, init, telemetry.

Nothing here opens a space for real but ``init``: the presets and the hold
are swapped for recorders, so a test sees what a command asked for.
"""

from __future__ import annotations

import asyncio
import json
import sys

import pytest
from click.testing import CliRunner

import nu
from nuspace import ops
from nuspace._cli import cli
from nuspace._cli.commands import demo as demo_command
from nuspace._cli.commands import run as run_command
from nuspace.host import presets
from nuspace.system import home
from nuspace.system.kernel import KERNEL_FILE, store
from nuspace.system.utils import snap


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    """A HOME of its own, so no test touches the real ``~/.nuspace``."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("NUSPACE_TELEMETRY", raising=False)
    monkeypatch.delenv("NUSPACE_STORE", raising=False)


def _invoke(*args: str, **kwargs):
    result = CliRunner().invoke(cli, list(args), **kwargs)
    return result


class _Recorder:
    """Stands in for a preset: records the call, returns a marker term."""

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs) -> str:
        self.calls.append((args, kwargs))
        return "term"


@pytest.fixture
def held(monkeypatch):
    """The terms the commands would hold, in order. Nothing is run."""
    terms: list = []
    for module in (run_command, demo_command):
        monkeypatch.setattr(module, "hold", terms.append)
    return terms


# --- Help and version ------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--help"],
        ["-h"],
        ["run", "--help"],
        ["demo", "--help"],
        ["init", "--help"],
        ["doctor", "--help"],
        ["telemetry", "--help"],
    ],
)
def test_help(args):
    result = _invoke(*args)
    assert result.exit_code == 0, result.output
    assert "Usage" in result.output


def test_commands_are_the_surface():
    assert set(cli.commands) == {"run", "demo", "init", "doctor", "telemetry"}


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version(flag):
    result = _invoke(flag)
    assert result.exit_code == 0, result.output
    assert result.output.startswith("nuspace, version ")


# --- run -------------------------------------------------------------------------


def test_run_serves_by_default(monkeypatch, held):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(presets, "serve", serve)
    monkeypatch.setattr(presets, "headless", headless)
    result = _invoke("run", "/tmp/space", "--host", "localhost", "-p", "9001", "--no-browser")
    assert result.exit_code == 0, result.output
    assert serve.calls == [
        (("/tmp/space",), {"host": "localhost", "port": 9001, "open_browser": False})
    ]
    assert headless.calls == []
    assert held == ["term"]


def test_run_headless_maps_to_the_headless_preset(monkeypatch, held):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(presets, "serve", serve)
    monkeypatch.setattr(presets, "headless", headless)
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((None,), {})]
    assert serve.calls == []
    assert "Headless" in result.output
    assert held == ["term"]


def test_run_takes_the_path_from_the_environment(monkeypatch, held):
    headless = _Recorder()
    monkeypatch.setattr(presets, "headless", headless)
    result = _invoke("run", "--headless", env={"NUSPACE_STORE": "/tmp/from-env"})
    assert result.exit_code == 0, result.output
    assert headless.calls == [(("/tmp/from-env",), {})]


def test_run_refuses_an_old_store(tmp_path, held):
    (tmp_path / "CURRENT").write_text("MANIFEST-000001\n")
    result = _invoke("run", "--headless", str(tmp_path))
    assert result.exit_code == 1
    assert "RocksDB" in result.output
    assert held == []


# --- demo ------------------------------------------------------------------------


def test_demo_lists_the_demos():
    pytest.importorskip("nuverse_demos")
    result = _invoke("demo")
    assert result.exit_code == 0, result.output
    for name in demo_command.demos() or {}:
        assert name in result.output


def test_demo_without_the_extra_says_how_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "nuverse_demos", None)
    result = _invoke("demo")
    assert result.exit_code == 1
    assert demo_command.INSTALL_HINT in result.output


def test_demo_refuses_an_unknown_name():
    pytest.importorskip("nuverse_demos")
    result = _invoke("demo", "nope")
    assert result.exit_code == 2
    assert "Unknown demo" in result.output


def test_demo_opens_the_named_plane(monkeypatch, held):
    pytest.importorskip("nuverse_demos")
    found = demo_command.demos() or {}
    name, spec = next(iter(found.items()))
    opened = _Recorder()
    monkeypatch.setattr(presets, "demo", opened)
    result = _invoke("demo", name, "-p", "9002", "--no-browser")
    assert result.exit_code == 0, result.output
    assert opened.calls == [
        ((spec, None), {"host": "127.0.0.1", "port": 9002, "open_browser": False})
    ]
    assert f"/{presets.demo_id(spec)}" in result.output
    assert held == ["term"]


# --- init ------------------------------------------------------------------------


def test_init_makes_a_space_and_seeds_it(tmp_path):
    path = tmp_path / "space"
    result = _invoke("init", str(path))
    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output
    assert (path / KERNEL_FILE).is_file()
    seeded = nu.With(store(str(path)), body=snap(ops.plane_exists(home.PLANE)))
    value, _ = asyncio.run(nu.arun(seeded))
    assert value is True

    again = _invoke("init", str(path))
    assert again.exit_code == 0, again.output
    assert "Already a space" in again.output


def test_init_refuses_an_old_store(tmp_path):
    (tmp_path / "CURRENT").write_text("MANIFEST-000001\n")
    result = _invoke("init", str(tmp_path))
    assert result.exit_code == 1
    assert "RocksDB" in result.output


# --- doctor ----------------------------------------------------------------------


def test_doctor_reports():
    result = _invoke("doctor")
    assert result.exit_code == 0, result.output
    for row in ("runtime", "nustd", "web bundle", "demos", "telemetry"):
        assert row in result.output


# --- telemetry -------------------------------------------------------------------


def _config(tmp_path) -> dict:
    return json.loads((tmp_path / "home" / ".nuspace" / "config.json").read_text())


def test_telemetry_status_is_on_by_default(tmp_path):
    result = _invoke("telemetry")
    assert result.exit_code == 0, result.output
    assert "telemetry: on" in result.output
    assert _config(tmp_path)["distinct_id"] in result.output


def test_telemetry_off_and_on(tmp_path):
    assert _invoke("telemetry", "off").exit_code == 0
    assert _config(tmp_path)["telemetry"] is False
    assert "telemetry: off" in _invoke("telemetry", "status").output
    did = _config(tmp_path)["distinct_id"]

    assert _invoke("telemetry", "on").exit_code == 0
    assert _config(tmp_path) == {"telemetry": True, "distinct_id": did}
    assert "telemetry: on" in _invoke("telemetry", "status").output


def test_telemetry_status_names_the_environment_override():
    result = _invoke("telemetry", "status", env={"NUSPACE_TELEMETRY": "0"})
    assert "telemetry: off" in result.output
    assert "NUSPACE_TELEMETRY" in result.output
