"""The command line: help and version, each command wired to its local entry point, init, verse, telemetry.

Nothing here opens a space for real but ``init`` and the refusals: the
entry points and the hold are swapped for recorders, so a test sees what a
command asked for. A real ``nuspace run`` and its Ctrl+C are in test_space.
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
from _support.contents import NoteContent
from click.testing import CliRunner

import nu
import nuspace
import nustd.kv
from nuspace._cli import _installed, cli
from nuspace._cli.commands import run as run_command
from nuspace._telemetry import config
from nuspace.shapes import Space
from nuspace.shapes.stores import CORE
from nuspace.space import local
from nuspace.space.blocks.meta import DATA_DIR
from nuspace.space.local.layout import STORES
from nuspace.specs import CellSpec, ContentSpec, Extension, PlaneSpec
from nuspace.web import WEB_STORE, Web


#: The Space store's file in a space's data dir: what a space made before ``meta.json`` is told by.
SPACE_FILE = STORES[Space].file


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    """A HOME of its own, so no test touches the real ``~/.nuspace``, and a cwd under it."""
    home = tmp_path / "home"
    (home / "work").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(home / "work")
    for name in (config.ENV, *config._OFF_WHEN_SET):
        monkeypatch.delenv(name, raising=False)


def _abs(path: str) -> str:
    return str(Path(path).resolve())


def _home_root(tmp_path) -> str:
    return str((tmp_path / "home").resolve())


def _invoke(*args: str, **kwargs):
    result = CliRunner().invoke(cli, list(args), **kwargs)
    return result


def _said(result) -> str:
    """The output with rich's box and wrapping taken out, one line of words."""
    return " ".join(result.output.replace("│", " ").split())


class _Recorder:
    """Stands in for an entry point: records the call, returns a marker term."""

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


def _plane(name: str, description: str = "") -> PlaneSpec:
    return PlaneSpec(name, name.capitalize(), description=description, backend="async")


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
                (_plane("chat", "Talk."), _plane("jobs")),
                (CellSpec("text", "Text", "1"),),
                (ContentSpec(NoteContent, description="Notes."),),
            ),
        ),
        _point("agents", "0.1.0", lambda: Extension((_plane("chat"), _plane("crew")))),
        _point("broken", "0.0.1", _broken),
    ]
    monkeypatch.setattr(_installed, "entry_points", lambda *, group: points)
    return points


@pytest.fixture
def verse_default(verse):
    """:func:`verse` with the default package too, adding a ``jobs`` plane as ``tools`` does."""
    ext = Extension((_plane("jobs", "Queue."), _plane("runs")))
    verse.append(_point(_installed.DEFAULT_PACKAGE, "0.3.4", lambda: ext))
    return verse


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


def test_run_runs_kernel_and_web_by_default(monkeypatch, held):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(local, "run", serve)
    monkeypatch.setattr(local, "kernel", headless)
    result = _invoke("run", "/tmp/space", "--host", "localhost", "-p", "9001", "--no-browser")
    assert result.exit_code == 0, result.output
    assert serve.calls == [
        (
            (_abs("/tmp/space"),),
            {"plane": None, "host": "localhost", "port": 9001, "open_browser": False},
        )
    ]
    assert headless.calls == []
    assert held == ["term"]


def test_run_headless_maps_to_the_kernel_alone(monkeypatch, held, tmp_path):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(local, "run", serve)
    monkeypatch.setattr(local, "kernel", headless)
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((_home_root(tmp_path),), {"body": None})]
    assert serve.calls == []
    assert "headless" in result.output
    assert held == ["term"]


@pytest.fixture
def listening():
    """A socket listening on a loopback port, so that port is taken."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        yield s.getsockname()[1]


def test_run_refuses_a_taken_port_given(monkeypatch, held, listening):
    serve = _Recorder()
    monkeypatch.setattr(local, "run", serve)
    result = _invoke("run", "/tmp/space", "-p", str(listening), "--no-browser")
    assert result.exit_code == 1, result.output
    assert f"Port {listening}" in _said(result)
    assert "taken" in _said(result)
    assert serve.calls == []
    assert held == []


def test_run_without_a_port_takes_the_first_free_from_8080(monkeypatch, held):
    serve = _Recorder()
    monkeypatch.setattr(local, "run", serve)
    monkeypatch.setattr(run_command, "_bindable", lambda host, port: port >= 8082)
    result = _invoke("run", "/tmp/space", "--no-browser")
    assert result.exit_code == 0, result.output
    assert serve.calls == [
        (
            (_abs("/tmp/space"),),
            {"plane": None, "host": "127.0.0.1", "port": 8082, "open_browser": False},
        )
    ]


# --- which space -------------------------------------------------------------------


@pytest.fixture
def headless(monkeypatch, held):
    """The kernel entry point, recorded: what ``run --headless`` was asked to open."""
    recorder = _Recorder()
    monkeypatch.setattr(local, "kernel", recorder)
    return recorder


def _space(root) -> None:
    """``root`` made a space as one was before ``meta.json``: its Space store file in ``.nuspace/``.

    Found the same as a space with its meta: the bridge local adopts.
    """
    (root / DATA_DIR / SPACE_FILE).parent.mkdir(parents=True)
    (root / DATA_DIR / SPACE_FILE).touch()


def test_run_opens_the_path_given(headless, tmp_path):
    result = _invoke("run", "--headless", "rel")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((str(tmp_path / "home" / "work" / "rel"),), {"body": None})]
    assert "~/work/rel" in result.output


def test_run_finds_the_nearest_space_up(headless, tmp_path, monkeypatch):
    root = tmp_path / "home" / "work"
    _space(root)
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((str(root),), {"body": None})]
    assert "~/work" in result.output


def test_run_falls_back_to_the_home_space(headless, tmp_path):
    """No space up from here: home, though its .nuspace holds only the user's config."""
    (tmp_path / "home" / DATA_DIR).mkdir()
    (tmp_path / "home" / DATA_DIR / "config.json").write_text("{}")
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((_home_root(tmp_path),), {"body": None})]
    assert "Path: ~/.nuspace" in _said(result)


def test_run_tmp_is_a_throwaway(headless):
    result = _invoke("run", "--headless", "--tmp")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((None,), {"body": None})]
    assert "throwaway" in result.output


def test_run_refuses_a_path_and_tmp(headless):
    result = _invoke("run", "--headless", "--tmp", "here")
    assert result.exit_code == 2
    assert "not both" in result.output
    assert headless.calls == []


@pytest.mark.parametrize("old", ["CURRENT", f"{DATA_DIR}/kernel.sqlite"])
def test_run_refuses_a_space_of_an_older_format(tmp_path, old):
    """Refused at open, before the lock, the server or a store: nothing is made."""
    (tmp_path / old).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / old).write_text("old\n")
    result = _invoke("run", "--headless", str(tmp_path))
    assert result.exit_code == 1, result.output
    assert "older nuspace store format" in _said(result)
    assert not (tmp_path / DATA_DIR / SPACE_FILE).exists()


# --- run --with ---------------------------------------------------------------


def test_run_from_opens_the_named_plane(monkeypatch, held, verse, tmp_path):
    opened = _Recorder()
    monkeypatch.setattr(local, "run", opened)
    result = _invoke("run", "--with", "agents.crew", "-p", "9002", "--no-browser")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    assert (kwargs.pop("plane").name, args[0]) == ("agents.crew", _home_root(tmp_path))
    assert kwargs == {"host": "127.0.0.1", "port": 9002, "open_browser": False}
    assert "plane agents.crew" in result.output
    assert held == ["term"]


def test_run_from_tells_apart_two_packages_sharing_a_name(monkeypatch, held, verse):
    opened = _Recorder()
    monkeypatch.setattr(local, "kernel", opened)
    result = _invoke("run", "/tmp/space", "--with", "tools.chat", "--headless")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    # Headless, the kernel makes the plane beside its driver.
    assert args == (_abs("/tmp/space"),)
    assert kwargs["body"] is not None
    assert "plane tools.chat" in result.output
    assert "headless" in result.output


@pytest.mark.parametrize("plane", ["agents.jobs", "nobody.chat", ".chat", "agents."])
def test_run_from_refuses_anything_but_an_installed_pkg_plane(held, verse_default, plane):
    result = _invoke("run", "--with", plane)
    assert result.exit_code == 1
    assert "pkg.plane" in result.output
    assert "nuspace verse" in result.output
    assert held == []


def test_run_from_takes_a_bare_name_as_a_nuverse_plane(monkeypatch, held, verse_default):
    opened = _Recorder()
    monkeypatch.setattr(local, "run", opened)
    result = _invoke("run", "--with", "jobs", "-p", "9003")
    assert result.exit_code == 0, result.output
    ((_, kwargs),) = opened.calls
    assert (kwargs["plane"].name, kwargs["plane"].description) == ("nuverse.jobs", "Queue.")
    assert _installed.resolve("jobs") == _installed.resolve("nuverse.jobs")
    assert _installed.resolve("tools.jobs").name == "tools.jobs"


@pytest.mark.parametrize("plane", ["chat", "crew", "tools:chat", ""])
def test_run_from_refuses_a_bare_name_nuverse_lacks_listing_its_planes(held, verse_default, plane):
    result = _invoke("run", "--with", plane)
    assert result.exit_code == 1
    said = _said(result)
    assert f"No plane {plane!r} in nuverse, where a bare name is looked up" in said
    assert "Its planes: jobs, runs." in said
    assert "nuspace verse" in said
    assert held == []


def test_run_from_says_so_when_nuverse_is_missing(held, verse):
    result = _invoke("run", "--with", "jobs")
    assert result.exit_code == 1
    assert "nuverse is not installed" in _said(result)
    assert held == []


def test_a_bare_name_resolves_against_the_real_nuverse():
    """nuverse always comes with nuspace, so its planes resolve bare."""
    for name in ("jobs", "runs", "workers", "planes"):
        assert _installed.resolve(name) == _installed.resolve(f"nuverse.{name}")


# --- init ------------------------------------------------------------------------


def _read(root: Path, term: nu.Nu) -> object:
    """``term`` read from the space at ``root``, its core and web stores opened plain."""
    data = root / DATA_DIR
    navs = [
        nustd.kv.sqlite_navigator(str(data / STORES[s.root].file), tags=(s.root,))
        for s in (*CORE, WEB_STORE)
    ]
    value, _ = asyncio.run(nu.arun(nu.With(*navs, body=nuspace.atomic(term))))
    return value


def test_init_makes_a_space_and_seeds_it(tmp_path):
    path = tmp_path / "space"
    result = _invoke("init", str(path))
    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output
    assert (path / DATA_DIR / SPACE_FILE).is_file()
    assert _read(path, nuspace.plane.exists(Web.roles["home"])) is True

    again = _invoke("init", str(path))
    assert again.exit_code == 0, again.output
    assert "Already a space" in again.output


def test_init_makes_the_current_directory_a_space(tmp_path):
    result = _invoke("init")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "home" / "work" / DATA_DIR / SPACE_FILE).is_file()
    assert "inside the space" not in result.output
    assert "nuspace run" in result.output


def test_init_warns_inside_another_space(tmp_path, monkeypatch):
    outer = tmp_path / "home" / "work"
    _space(outer)
    inner = outer / "inner"
    inner.mkdir()
    monkeypatch.chdir(inner)
    result = _invoke("init")
    assert result.exit_code == 0, result.output
    assert "inside the space at ~/work" in _said(result)
    assert (inner / DATA_DIR / SPACE_FILE).is_file()


def test_init_keeps_quiet_about_the_home_space(tmp_path):
    _space(tmp_path / "home")
    result = _invoke("init")
    assert result.exit_code == 0, result.output
    assert "inside the space" not in result.output


def test_init_refuses_a_space_of_an_older_format(tmp_path):
    (tmp_path / DATA_DIR).mkdir()
    (tmp_path / DATA_DIR / "kernel.sqlite").touch()
    result = _invoke("init", str(tmp_path))
    assert result.exit_code == 1
    assert "older nuspace store format" in _said(result)


# --- verse -----------------------------------------------------------------------


def test_verse_lists_each_package_and_its_planes(verse):
    result = _invoke("verse")
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].split() == [
        "tools",
        "1.2.0",
        "chat",
        "·",
        "jobs",
        "+1",
        "cells",
        "+1",
        "content",
        "kinds",
    ]
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
    assert tools["contents"] == [{"name": "tools.Note", "label": "Note", "description": "Notes."}]
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
