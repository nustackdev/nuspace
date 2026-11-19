"""The command line: help and version, each command wired to its assembly's entry point, init, verse, telemetry.

Nothing here opens a space for real but ``init`` and the refusals: the
entry points and the hold are swapped for recorders, so a test sees what a
command asked for. ``run`` puts the entry point's term after its init;
:func:`_peel` takes that off again. A throwaway root is a term known only
once it runs, so a test of one, or one that needs the init to happen,
holds the term for real, over recorded entry points that run nothing. A real ``nuspace run`` and its
Ctrl+C are in test_space.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from _support.contents import NoteContent
from click.testing import CliRunner

import nu
import nuspace
import nustd.kv
from nu.core.flows import Sequential
from nuspace._cli import _installed, cli
from nuspace._cli._meta import EXIT
from nuspace._cli.commands import run as run_command
from nuspace._telemetry import config
from nuspace.shapes import Space
from nuspace.shapes.stores import CORE
from nuspace.space import local
from nuspace.space.blocks.meta import DATA_DIR, META_FILE
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


#: What a recorded entry point returns: a term that does nothing, held for real or not.
MARK = nu.Noop()


class _Recorder:
    """Stands in for an entry point: records the call, returns :data:`MARK` or ``returns``."""

    def __init__(self, returns: object = None) -> None:
        self.calls: list[tuple[tuple, dict]] = []
        self.returns = returns

    def __call__(self, *args, **kwargs) -> object:
        self.calls.append((args, kwargs))
        if callable(self.returns):
            return self.returns(*args, **kwargs)
        return MARK if self.returns is None else self.returns


def _peel(term: nu.Nu) -> nu.Nu:
    """What ``run`` held, unwrapped: the entry point's term, the init before it taken off."""
    if isinstance(term, Sequential):
        _, term = term._children
    return term


class Held(list):
    """The entry points' terms the commands would hold, unwrapped, in order. Nothing is held."""

    def hold(self, term: nu.Nu) -> int:
        self.append(_peel(term))
        return 0


def _meta(root: Path) -> dict:
    """What the space at ``root`` holds in its ``meta.json``."""
    return json.loads((Path(root) / DATA_DIR / META_FILE).read_text())


def _write_meta(root: Path, **fields: object) -> None:
    """``root`` a space whose ``meta.json`` holds ``fields``."""
    (Path(root) / DATA_DIR).mkdir(parents=True, exist_ok=True)
    (Path(root) / DATA_DIR / META_FILE).write_text(json.dumps(fields) + "\n")


@pytest.fixture
def held(monkeypatch):
    """:class:`Held`: what the commands would hold. Nothing runs, no init either."""
    terms = Held()
    monkeypatch.setattr(run_command, "hold", terms.hold)
    return terms


@pytest.fixture
def inits(monkeypatch):
    """The roots ``nuspace run`` puts local's init before, in order. Recorded at build, never run."""
    recorder = _Recorder()
    monkeypatch.setattr(local, "init", recorder)
    return recorder.calls


def _roots(calls) -> list[str]:
    return [args[0] for args, _ in calls]


@pytest.fixture
def entries(monkeypatch):
    """Every entry point of local but ``init``, recorded, by name."""
    recorders = {name: _Recorder() for name in ("run", "infra", "kernel", "web", "open")}
    for name, recorder in recorders.items():
        monkeypatch.setattr(local, name, recorder)
    return recorders


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


def test_run_runs_kernel_and_web_by_default(monkeypatch, held, inits):
    serve, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(local, "run", serve)
    monkeypatch.setattr(local, "kernel", headless)
    result = _invoke("run", "/tmp/space", "--host", "localhost", "-p", "9001", "--no-browser")
    assert result.exit_code == 0, result.output
    assert serve.calls == [
        (
            (_abs("/tmp/space"),),
            {
                "into": EXIT,
                "plane": None,
                "host": "localhost",
                "port": 9001,
                "open_browser": False,
            },
        )
    ]
    assert headless.calls == []
    assert held == [MARK]
    assert _roots(inits) == [_abs("/tmp/space")]


def test_run_headless_maps_to_infra_around_the_kernel(monkeypatch, held, inits, tmp_path):
    serve, headless, infra = _Recorder(), _Recorder(), _Recorder()
    monkeypatch.setattr(local, "run", serve)
    monkeypatch.setattr(local, "kernel", headless)
    monkeypatch.setattr(local, "infra", infra)
    result = _invoke("run", "--headless")
    assert result.exit_code == 0, result.output
    assert headless.calls == [((_home_root(tmp_path),), {"body": None})]
    assert infra.calls == [((_home_root(tmp_path),), {"body": MARK})]
    assert serve.calls == []
    assert "headless" in result.output
    assert held == [MARK]
    assert _roots(inits) == [_home_root(tmp_path)]


def test_run_web_maps_to_web_alone(monkeypatch, held, inits):
    serve, headless, web = _Recorder(), _Recorder(), _Recorder()
    monkeypatch.setattr(local, "run", serve)
    monkeypatch.setattr(local, "kernel", headless)
    monkeypatch.setattr(local, "web", web)
    result = _invoke("run", "/tmp/space", "--web", "-p", "9004", "--no-browser")
    assert result.exit_code == 0, result.output
    assert web.calls == [
        (
            (_abs("/tmp/space"),),
            {"plane": None, "host": "127.0.0.1", "port": 9004, "open_browser": False},
        )
    ]
    assert serve.calls == headless.calls == []
    assert held == [MARK]
    assert inits == []


def test_run_refuses_headless_and_web_together(monkeypatch, held):
    web, headless = _Recorder(), _Recorder()
    monkeypatch.setattr(local, "web", web)
    monkeypatch.setattr(local, "kernel", headless)
    result = _invoke("run", "/tmp/space", "--web", "--headless")
    assert result.exit_code == 2
    assert "not both" in result.output
    assert web.calls == headless.calls == []
    assert held == []


@pytest.mark.parametrize("args", [["--no-browser", "-p", "9006"], ["--headless"]])
def test_run_on_a_fresh_directory_initializes_it_then_runs(entries, tmp_path, args):
    """Held for real: local's init runs, then the recorded entry point, which runs nothing."""
    path = tmp_path / "fresh"
    result = _invoke("run", str(path), *args)
    assert result.exit_code == 0, result.output
    assert _meta(path)["init"] is True
    assert (path / DATA_DIR / SPACE_FILE).is_file()
    ran = "kernel" if "--headless" in args else "run"
    assert [a for a, _ in entries[ran].calls] == [(str(path),)]


def test_run_does_not_init_a_space_initialized_already(monkeypatch, entries, tmp_path):
    """Held for real: the init step looks at meta.json when it runs and leaves an initialized space."""
    monkeypatch.setattr(local, "init", _Recorder(lambda root: nu.print(f"init ran on {root}")))
    _write_meta(tmp_path, assembly="local", made_at="2026-11-19T00:00:00+00:00", init=True)
    result = _invoke("run", str(tmp_path), "--headless")
    assert result.exit_code == 0, result.output
    assert "init ran" not in result.output
    assert [a for a, _ in entries["kernel"].calls] == [(str(tmp_path),)]


@pytest.mark.parametrize("flag", ["--infra", "--kernel", "--web"])
def test_one_component_on_a_fresh_directory_is_refused(tmp_path, flag):
    """Never initialized for it: the entry point's own check refuses, before anything is made."""
    path = tmp_path / "fresh"
    result = _invoke("run", str(path), flag, "--no-browser")
    assert result.exit_code == 1, result.output
    said = _said(result)
    assert "is not initialized: run nuspace init, or local.init" in said
    assert "Traceback" not in result.output
    assert not (path / DATA_DIR).exists()


@pytest.mark.parametrize(
    ("args", "called"),
    [
        (
            [],
            {
                "run": {
                    "into": EXIT,
                    "plane": None,
                    "host": "127.0.0.1",
                    "port": 9007,
                    "open_browser": False,
                }
            },
        ),
        (["--headless"], {"infra": {"body": MARK}, "kernel": {"body": None}}),
        (["--infra"], {"infra": {}}),
        (["--kernel"], {"kernel": {"body": None}}),
        (
            ["--web"],
            {"web": {"plane": None, "host": "127.0.0.1", "port": 9007, "open_browser": False}},
        ),
    ],
)
def test_each_way_to_run_builds_its_term(held, inits, entries, tmp_path, args, called):
    result = _invoke("run", str(tmp_path), *args, "-p", "9007", "--no-browser")
    assert result.exit_code == 0, result.output
    got = {name: r.calls for name, r in entries.items() if r.calls}
    assert got == {name: [((str(tmp_path),), kwargs)] for name, kwargs in called.items()}
    assert held == [MARK]
    alone = {"--infra", "--kernel", "--web"} & set(args)
    assert _roots(inits) == ([] if alone else [str(tmp_path)])


def test_kernel_alone_makes_the_plane_with_in_its_body(held, inits, entries, verse):
    result = _invoke("run", "/tmp/space", "--kernel", "--with", "tools.chat")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = entries["kernel"].calls
    assert args == (_abs("/tmp/space"),)
    assert kwargs["body"] is not None
    assert "kernel alone" in result.output
    assert inits == []


@pytest.mark.parametrize(
    ("args", "said"),
    [
        (["--infra", "--kernel"], "Give one of --infra, --kernel or --web"),
        (["--kernel", "--web"], "Give one of --infra, --kernel or --web"),
        (["--infra", "--web"], "Give one of --infra, --kernel or --web"),
        (["--infra", "--kernel", "--web"], "Give one of --infra, --kernel or --web"),
        (["--infra", "--headless"], "Give --headless or --infra, not both"),
        (["--kernel", "--headless"], "Give --headless or --kernel, not both"),
        (["--web", "--headless"], "Give --headless or --web, not both"),
        (["--infra", "--tmp"], "--tmp with --infra"),
        (["--kernel", "--tmp"], "--tmp with --kernel"),
        (["--web", "--tmp"], "--tmp with --web"),
        (["--infra", "--with", "jobs"], "infra alone"),
    ],
)
def test_run_refuses_flags_that_do_not_go_together(held, inits, entries, args, said):
    result = _invoke("run", *args)
    assert result.exit_code == 2, result.output
    assert said in _said(result)
    assert all(r.calls == [] for r in entries.values())
    assert held == inits == []


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
            {
                "into": EXIT,
                "plane": None,
                "host": "127.0.0.1",
                "port": 8082,
                "open_browser": False,
            },
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


def _seen(ran: list[tuple[str, str]], name: str) -> _Recorder:
    """An entry point that, when it runs, says it ran on its root, then runs its body when given."""
    saw = nu.host(lambda root: ran.append((name, root)), name=f"Saw{name.capitalize()}")

    def entry(root: nu.Nu, body: nu.Nu | None = None, **_: object) -> nu.Nu:
        return saw(root) if body is None else saw(root) >> body

    return _Recorder(entry)


@pytest.mark.parametrize("args", [["--headless", "--tmp"], ["--tmp", "--no-browser"]])
def test_run_tmp_is_a_throwaway_initialized_then_removed(monkeypatch, args):
    """Held for real: one throwaway root for whatever runs on it, its init first, gone at close."""
    ran: list[tuple[str, str]] = []
    for name in ("init", "run", "infra", "kernel"):
        monkeypatch.setattr(local, name, _seen(ran, name))
    result = _invoke("run", *args)
    assert result.exit_code == 0, result.output
    names = [name for name, _ in ran]
    assert names == (["init", "infra", "kernel"] if "--headless" in args else ["init", "run"])
    (root,) = {root for _, root in ran}
    assert Path(root).name.startswith("nuspace-")
    assert not Path(root).exists()
    assert "throwaway" in result.output


def test_run_tmp_removes_the_throwaway_it_initialized(monkeypatch, entries):
    """Held for real: initialized while the entry point runs, gone once the hold ends."""
    seen: list[tuple[str, bool]] = []
    looked = nu.host(lambda root: seen.append((root, _meta(root)["init"])), name="Looked")
    monkeypatch.setattr(local, "run", _Recorder(lambda root, **_: looked(root)))
    result = _invoke("run", "--tmp", "--no-browser")
    assert result.exit_code == 0, result.output
    ((root, init),) = seen
    assert init is True
    assert not Path(root).exists()


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


# --- which assembly ---------------------------------------------------------------


def _made_by(root: Path, name: str) -> None:
    """``root`` a space whose ``meta.json`` names the assembly ``name``."""
    _write_meta(root, assembly=name, made_at="2026-11-18T00:00:00+00:00")


def test_run_calls_the_assembly_meta_json_names(monkeypatch, held, tmp_path):
    kernel = _Recorder()
    other = SimpleNamespace(
        run=_Recorder(),
        infra=_Recorder(),
        kernel=kernel,
        web=_Recorder(),
        open=None,
        init=_Recorder(),
    )
    monkeypatch.setitem(sys.modules, "nuspace.space.other", other)
    _made_by(tmp_path, "other")
    result = _invoke("run", "--headless", str(tmp_path))
    assert result.exit_code == 0, result.output
    assert kernel.calls == [((str(tmp_path),), {"body": None})]
    assert other.init.calls == [((str(tmp_path),), {})]
    assert held == [MARK]


@pytest.mark.parametrize("name", ["nowhere", "blocks", "../local", ""])
def test_run_refuses_an_assembly_that_does_not_import(headless, tmp_path, name):
    _made_by(tmp_path, name)
    result = _invoke("run", "--headless", str(tmp_path))
    assert result.exit_code == 1, result.output
    assert repr(name) in _said(result)
    assert "Traceback" not in result.output
    assert headless.calls == []


def test_init_refuses_an_assembly_that_does_not_import(tmp_path):
    _made_by(tmp_path, "nowhere")
    result = _invoke("init", str(tmp_path))
    assert result.exit_code == 1, result.output
    assert "'nowhere' does not import" in _said(result)
    assert not (tmp_path / DATA_DIR / SPACE_FILE).exists()


def test_run_refuses_a_meta_json_that_does_not_read(headless, tmp_path):
    (tmp_path / DATA_DIR).mkdir()
    (tmp_path / DATA_DIR / "meta.json").write_text("{")
    result = _invoke("run", "--headless", str(tmp_path))
    assert result.exit_code == 1, result.output
    assert "does not read" in _said(result)
    assert headless.calls == []


def test_a_new_space_and_a_throwaway_are_local(monkeypatch, held, tmp_path):
    kernel = _Recorder()
    monkeypatch.setattr(local, "kernel", kernel)
    assert _invoke("run", "--headless", str(tmp_path / "new")).exit_code == 0
    assert _invoke("run", "--headless", "--tmp").exit_code == 0
    ((new,), (throwaway,)) = [args for args, _ in kernel.calls]
    assert new == str(tmp_path / "new")
    # The throwaway's root is known once it runs: the kernel is handed a term yielding it.
    assert isinstance(throwaway, nu.Nu)


# --- run --with ---------------------------------------------------------------


def test_run_from_opens_the_named_plane(monkeypatch, held, verse, tmp_path):
    opened = _Recorder()
    monkeypatch.setattr(local, "run", opened)
    result = _invoke("run", "--with", "agents.crew", "-p", "9002", "--no-browser")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = opened.calls
    assert (kwargs.pop("plane").name, args[0]) == ("agents.crew", _home_root(tmp_path))
    assert kwargs == {"into": EXIT, "host": "127.0.0.1", "port": 9002, "open_browser": False}
    assert "plane agents.crew" in result.output
    assert held == [MARK]


def test_run_web_with_opens_the_named_plane(monkeypatch, held, verse):
    web = _Recorder()
    monkeypatch.setattr(local, "web", web)
    result = _invoke("run", "/tmp/space", "--web", "--with", "agents.crew", "-p", "9005")
    assert result.exit_code == 0, result.output
    ((args, kwargs),) = web.calls
    assert (args, kwargs.pop("plane").name) == ((_abs("/tmp/space"),), "agents.crew")
    assert kwargs == {"host": "127.0.0.1", "port": 9005, "open_browser": True}


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
    assert _meta(path)["assembly"] == "local"
    assert _read(path, nuspace.plane.exists(Web.roles["home"])) is True

    assert _meta(path)["init"] is True

    again = _invoke("init", str(path))
    assert again.exit_code == 0, again.output
    assert "Already initialized" in again.output


def test_init_initializes_a_space_made_but_not_initialized(tmp_path):
    """A meta.json without the flag, or a space made before meta.json: init runs, and says so."""
    made, before = tmp_path / "made", tmp_path / "before"
    _made_by(made, "local")
    _space(before)
    for path in (made, before):
        result = _invoke("init", str(path))
        assert result.exit_code == 0, result.output
        assert "Initialized a space" in result.output
        assert _meta(path)["init"] is True


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
