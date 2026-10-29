"""The command line: help and version, each command wired to its preset, init, verse, telemetry.

Nothing here opens a space for real but ``init``: the presets and the hold
are swapped for recorders, so a test sees what a command asked for.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from _support.contents import NoteContent
from click.testing import CliRunner

import nu
from nuspace import ops
from nuspace._cli import _installed, cli
from nuspace._cli.commands import run as run_command
from nuspace.ext import CellSpec, ContentSpec, Extension, PlaneSpec
from nuspace.host import presets
from nuspace.shapes import Space
from nuspace.system.kernel import DATA_DIR, KERNEL_FILE, STATE_FILE, VALKEY_DIR, store
from nuspace.system.kernel import space as kernel_space
from nuspace.system.ui import home
from nuspace.system.utils import snap


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    """A HOME of its own, so no test touches the real ``~/.nuspace``, and a cwd under it."""
    home = tmp_path / "home"
    (home / "work").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(home / "work")
    for name in ("NUSPACE_TELEMETRY", "DO_NOT_TRACK", "CI"):
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


def test_run_serves_by_default(monkeypatch, held):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(presets, "serve", serve)
    monkeypatch.setattr(presets, "headless", headless)
    result = _invoke("run", "/tmp/space", "--host", "localhost", "-p", "9001", "--no-browser")
    assert result.exit_code == 0, result.output
    assert serve.calls == [
        ((_abs("/tmp/space"),), {"host": "localhost", "port": 9001, "open_browser": False})
    ]
    assert headless.calls == []
    assert held == ["term"]


def test_run_headless_maps_to_the_headless_preset(monkeypatch, held, tmp_path):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(presets, "serve", serve)
    monkeypatch.setattr(presets, "headless", headless)
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((_home_root(tmp_path),), {})]
    assert serve.calls == []
    assert "headless" in result.output
    assert held == ["term"]


# --- which space -------------------------------------------------------------------


@pytest.fixture
def headless(monkeypatch, held):
    """The headless preset, recorded: what ``run --headless`` was asked to open."""
    recorder = _Recorder()
    monkeypatch.setattr(presets, "headless", recorder)
    return recorder


def _space(root) -> None:
    """``root`` made a space as far as finding one goes: its store file in ``.nuspace/``."""
    (root / DATA_DIR).mkdir(parents=True)
    (root / DATA_DIR / KERNEL_FILE).touch()


def test_run_opens_the_path_given(headless, tmp_path):
    result = _invoke("run", "--headless", "rel")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((str(tmp_path / "home" / "work" / "rel"),), {})]
    assert "~/work/rel" in result.output


def test_run_finds_the_nearest_space_up(headless, tmp_path, monkeypatch):
    root = tmp_path / "home" / "work"
    _space(root)
    nested = root / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((str(root),), {})]
    assert "~/work" in result.output


def test_run_falls_back_to_the_home_space(headless, tmp_path):
    """No space up from here: home, though its .nuspace holds only the user's config."""
    (tmp_path / "home" / DATA_DIR).mkdir()
    (tmp_path / "home" / DATA_DIR / "config.json").write_text("{}")
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((_home_root(tmp_path),), {})]
    assert "Path: ~/.nuspace" in _said(result)


def test_run_tmp_is_a_throwaway(headless):
    result = _invoke("run", "--headless", "--tmp")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((None,), {})]
    assert "throwaway" in result.output


def test_run_refuses_a_path_and_tmp(headless):
    result = _invoke("run", "--headless", "--tmp", "here")
    assert result.exit_code == 2
    assert "not both" in result.output
    assert headless.calls == []


def test_run_refuses_an_old_store(tmp_path, held):
    (tmp_path / "CURRENT").write_text("MANIFEST-000001\n")
    result = _invoke("run", "--headless", str(tmp_path))
    assert result.exit_code == 1
    assert "RocksDB" in result.output
    assert held == []


# --- run --with ---------------------------------------------------------------


def test_run_from_opens_the_named_plane(monkeypatch, held, verse, tmp_path):
    opened = _Recorder()
    monkeypatch.setattr(presets, "with_plane", opened)
    result = _invoke("run", "--with", "agents.crew", "-p", "9002", "--no-browser")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    assert (args[0].name, args[1]) == ("agents.crew", _home_root(tmp_path))
    assert kwargs == {"host": "127.0.0.1", "port": 9002, "open_browser": False}
    assert "plane agents.crew" in result.output
    assert held == ["term"]


def test_run_from_tells_apart_two_packages_sharing_a_name(monkeypatch, held, verse):
    opened = _Recorder()
    monkeypatch.setattr(presets, "with_plane", opened)
    result = _invoke("run", "/tmp/space", "--with", "tools.chat", "--headless")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    assert (args[0].name, args[0].description, args[1]) == (
        "tools.chat",
        "Talk.",
        _abs("/tmp/space"),
    )
    assert kwargs == {"web": False}
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
    monkeypatch.setattr(presets, "with_plane", opened)
    result = _invoke("run", "--with", "jobs", "--headless")
    assert result.exit_code == 0, result.output
    ((args, _),) = opened.calls
    assert (args[0].name, args[0].description) == ("nuverse.jobs", "Queue.")
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


def _run_with(path: str, *specs: PlaneSpec) -> None:
    """Open the space at ``path`` headless with each of ``specs`` in turn, for real."""
    for spec in specs:
        term = presets.with_plane(spec, path, web=False, extensions=())
        nu.eval_in_loop(nu.compile(nu.Race(term, nu.Delay(3.0))), nu.Context())


def _read(path: str, term: nu.Nu):
    value, _ = asyncio.run(nu.arun(nu.With(store(path), body=snap(term))))
    return value


def _made(path: str) -> dict:
    """What the space recorded: registered plane name to the plane id made for it."""
    return dict(_read(path, nu.Dict(Space.state.made.extract())))


def _made_by(path: str, name: str) -> list[str]:
    """The ids of the planes made from the Plane registered as ``name``."""
    planes = _read(path, nu.Dict(Space.planes.extract()))
    return [pid for pid, row in planes.items() if row["props"]["made_by"] == name]


_COUNTER = PlaneSpec("nudemos.counter", "Counter", cells=(("count", "1"),), backend="async")


def test_run_from_makes_the_plane_once(tmp_path):
    """The real thing, headless: the plane gets a minted id, recorded, and the second run reuses it."""
    path = str(tmp_path / "space")
    _run_with(path, _COUNTER)
    (plane,) = _made_by(path, "nudemos.counter")
    assert plane.startswith("p_")
    assert _made(path) == {"nudemos.counter": plane}
    _run_with(path, _COUNTER)
    assert _made_by(path, "nudemos.counter") == [plane]
    assert _made(path) == {"nudemos.counter": plane}
    assert len(_read(path, ops.cells(plane))) == 1


def test_run_from_makes_a_deleted_plane_again(tmp_path):
    path = str(tmp_path / "space")
    _run_with(path, _COUNTER)
    gone = _made(path)["nudemos.counter"]
    asyncio.run(nu.arun(nu.With(store(path), body=ops.remove_plane(gone))))
    assert _made_by(path, "nudemos.counter") == []
    _run_with(path, _COUNTER)
    (plane,) = _made_by(path, "nudemos.counter")
    assert plane != gone
    assert _made(path) == {"nudemos.counter": plane}


def test_run_from_keeps_one_record_per_plane(tmp_path):
    other = PlaneSpec("nudemos.movies", "Movies", backend="async")
    path = str(tmp_path / "space")
    _run_with(path, _COUNTER, other, _COUNTER, other)
    made = _made(path)
    assert set(made) == {"nudemos.counter", "nudemos.movies"}
    assert made["nudemos.counter"] != made["nudemos.movies"]
    assert _made_by(path, "nudemos.counter") == [made["nudemos.counter"]]
    assert _made_by(path, "nudemos.movies") == [made["nudemos.movies"]]


def test_run_from_a_bare_nuverse_name_records_it_under_its_full_name(tmp_path):
    path = str(tmp_path / "space")
    jobs = _installed.resolve("jobs")
    _run_with(path, jobs, jobs)
    made = _made(path)
    assert list(made) == ["nuverse.jobs"]
    assert _made_by(path, "nuverse.jobs") == [made["nuverse.jobs"]]


# --- init ------------------------------------------------------------------------


def test_init_makes_a_space_and_seeds_it(tmp_path):
    path = tmp_path / "space"
    result = _invoke("init", str(path))
    assert result.exit_code == 0, result.output
    assert "Initialized" in result.output
    assert (path / DATA_DIR / KERNEL_FILE).is_file()
    assert not (path / KERNEL_FILE).exists()
    seeded = nu.With(store(str(path)), body=snap(ops.plane_exists(home.PLANE)))
    value, _ = asyncio.run(nu.arun(seeded))
    assert value is True

    again = _invoke("init", str(path))
    assert again.exit_code == 0, again.output
    assert "Already a space" in again.output


def test_init_makes_the_current_directory_a_space(tmp_path):
    result = _invoke("init")
    assert result.exit_code == 0, result.output
    assert (tmp_path / "home" / "work" / DATA_DIR / KERNEL_FILE).is_file()
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
    assert (inner / DATA_DIR / KERNEL_FILE).is_file()


def test_init_keeps_quiet_about_the_home_space(tmp_path):
    _space(tmp_path / "home")
    result = _invoke("init")
    assert result.exit_code == 0, result.output
    assert "inside the space" not in result.output


def test_a_flat_space_moves_into_its_data_dir(tmp_path):
    """A space an older nuspace made, its files loose in the root: moved in on open, kept."""
    path = tmp_path / "old"
    assert _invoke("init", str(path)).exit_code == 0
    data = path / DATA_DIR
    for name in (KERNEL_FILE, STATE_FILE, VALKEY_DIR):
        (data / name).rename(path / name)
    data.rmdir()
    planes = _read(str(path), nu.Dict(Space.planes.extract()))
    assert planes
    assert (data / KERNEL_FILE).is_file()
    assert (data / STATE_FILE).is_file()
    assert not (path / KERNEL_FILE).exists()
    assert _invoke("init", str(path)).output.startswith("Already a space")


def test_a_flat_space_still_open_is_left_alone(tmp_path, monkeypatch):
    """An older nuspace holding it open: nothing moves, the error says what to do."""
    monkeypatch.setattr(kernel_space, "ping", lambda _: True)
    (tmp_path / KERNEL_FILE).touch()
    result = _invoke("init", str(tmp_path))
    assert result.exit_code == 1
    assert "Stop it and open again" in _said(result)
    assert (tmp_path / KERNEL_FILE).is_file()
    assert not (tmp_path / DATA_DIR).exists()


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
