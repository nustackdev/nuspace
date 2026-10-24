"""The command line: help and version, each command wired to its preset, init, verse, telemetry.

Nothing here opens a space for real but ``init``: the presets and the hold
are swapped for recorders, so a test sees what a command asked for.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

import nu
from nuspace import ops
from nuspace._cli import _installed, cli
from nuspace._cli.commands import run as run_command
from nuspace.ext import Cell, Extension, Plane
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
    monkeypatch.setattr(run_command, "hold", lambda term, **_: terms.append(term))
    return terms


def _plane(name: str, description: str = "") -> Plane:
    return Plane(name, name.capitalize(), description=description, backend="async")


def _point(name: str, version: str, load):
    """An entry point of a distribution at ``version``, loading to what ``load`` gives."""
    return SimpleNamespace(name=name, load=load, dist=SimpleNamespace(version=version))


def _broken():
    raise ImportError("no module named torch")


@pytest.fixture
def verse(monkeypatch):
    """Three packages installed, one broken: two add a plane named ``chat``."""
    points = [
        _point(
            "tools",
            "1.2.0",
            lambda: Extension(
                (_plane("chat", "Talk."), _plane("jobs")), (Cell("text", "Text", "1"),)
            ),
        ),
        _point("agents", "0.1.0", lambda: Extension((_plane("chat"), _plane("crew")))),
        _point("broken", "0.0.1", _broken),
    ]
    monkeypatch.setattr(_installed, "entry_points", lambda *, group: points)
    return points


# --- Help and version ------------------------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--help"],
        ["-h"],
        ["run", "--help"],
        ["init", "--help"],
        ["verse", "--help"],
        ["telemetry", "--help"],
    ],
)
def test_help(args):
    result = _invoke(*args)
    assert result.exit_code == 0, result.output
    assert "Usage" in result.output


def test_commands_are_the_surface():
    assert set(cli.commands) == {"init", "run", "verse", "telemetry"}


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version(flag):
    result = _invoke(flag)
    assert result.exit_code == 0, result.output
    assert result.output.startswith("nuspace ")
    assert " · nucore " in result.output
    assert " · nustd " in result.output


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
    assert "headless" in result.output
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


# --- run --with ---------------------------------------------------------------


def test_run_from_opens_the_named_plane(monkeypatch, held, verse):
    opened = _Recorder()
    monkeypatch.setattr(presets, "with_plane", opened)
    result = _invoke("run", "--with", "agents.crew", "-p", "9002", "--no-browser")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    assert (args[0].name, args[1]) == ("agents.crew", None)
    assert kwargs == {"host": "127.0.0.1", "port": 9002, "open_browser": False}
    assert "agents-crew" in result.output
    assert held == ["term"]


def test_run_from_tells_apart_two_packages_sharing_a_name(monkeypatch, held, verse):
    opened = _Recorder()
    monkeypatch.setattr(presets, "with_plane", opened)
    result = _invoke("run", "/tmp/space", "--with", "tools.chat", "--headless")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    assert (args[0].name, args[0].description, args[1]) == ("tools.chat", "Talk.", "/tmp/space")
    assert kwargs == {"web": False}
    assert "tools-chat" in result.output
    assert "headless" in result.output


@pytest.mark.parametrize(
    "plane", ["chat", "crew", "tools:chat", "agents.jobs", "nobody.chat", ".chat", "agents."]
)
def test_run_from_refuses_anything_but_an_installed_pkg_plane(held, verse, plane):
    result = _invoke("run", "--with", plane)
    assert result.exit_code == 1
    assert "nuspace verse" in result.output
    assert held == []


def test_run_from_makes_the_plane_once(tmp_path):
    """The real thing, headless: the plane lands under its fixed id, once."""
    spec = Plane("nudemos.counter", "Counter", cells=(("count", "1"),), backend="async")
    path = str(tmp_path / "space")
    for _ in range(2):
        term = presets.with_plane(spec, path, web=False, discover=False)
        nu.eval_in_loop(nu.compile(nu.Race(term, nu.Delay(3.0))), nu.Context())
    plane = presets.plane_id(spec)
    assert plane == "nudemos-counter"
    seeded = nu.With(store(path), body=snap(ops.cells(plane)))
    value, _ = asyncio.run(nu.arun(seeded))
    assert len(value) == 1


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


# --- verse -----------------------------------------------------------------------


def test_verse_lists_each_package_and_its_planes(verse):
    result = _invoke("verse")
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split() == ["tools", "1.2.0", "chat", "·", "jobs", "+1", "cells"]
    assert lines[1].split() == ["agents", "0.1.0", "chat", "·", "crew"]
    assert lines[2].split() == ["broken", "0.0.1"]
    assert "torch" in lines[3]
    assert len(lines) == 4


def test_verse_json_gives_the_detail(verse):
    result = _invoke("verse", "--json")
    assert result.exit_code == 0, result.output
    tools, agents, broken = json.loads(result.output)["packages"]
    assert tools["name"] == "tools"
    assert tools["version"] == "1.2.0"
    assert tools["planes"][0] == {"name": "tools.chat", "label": "Chat", "description": "Talk."}
    assert [s["name"] for s in tools["cells"]] == ["text"]
    assert tools["error"] is None
    assert [p["name"] for p in agents["planes"]] == ["agents.chat", "agents.crew"]
    assert broken["planes"] == []
    assert "torch" in broken["error"]


def test_verse_lists_what_is_really_installed():
    """nuverse always comes with nuspace."""
    result = _invoke("verse", "--json")
    names = [p["name"] for p in json.loads(result.output)["packages"]]
    assert "nuverse" in names


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


# --- header ----------------------------------------------------------------------


@pytest.mark.parametrize("size", ["sm", "md", "lg"])
def test_header_names_the_version_and_the_space(size):
    from rich.console import Console

    from nuspace._branding import header

    console = Console(width=120, record=True)
    console.print(header(size, version="9.9.9", where="~/space"))
    text = console.export_text()
    assert "nuspace 9.9.9" in text
    assert "~/space" in text
    assert len(text.splitlines()) == (1 if size == "sm" else 8)
