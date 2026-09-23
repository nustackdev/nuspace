"""The host: the registry, open_space headless with real workers, and the command line.

The registry is plain python. open_space runs once, headless, on a store
seeded the way a person would: a user plane added to init's boot list before
the space opens. The web variant is only compiled.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import warnings
from pathlib import Path

import pytest
from click.testing import CliRunner

import nu
import nustd.kv
from nuspace import App, Extension, Snippet, boot, open_space, ops
from nuspace.host import registry as registry_module
from nuspace.host.cli import cli
from nuspace.host.registry import GROUP, Registry, RegistryWarning, discover
from nuspace.host.space import space_registry
from nuspace.ops.utils import atomic
from nuspace.shapes import STATUS_UP, Reroot, Space, reroot
from nuspace.system.kernel import Env, store
from nuspace.system.kernel.body import Bracketed, Rewrites
from nuspace.system.services import BOOTED, SERVICES, ensure_system, init
from nuverse.snippets import program as nuverse_program
from nuverse.snippets import prose as nuverse_prose


sys.path.insert(0, str(Path(__file__).parent))
from test_kernel import SET_42, Kernel, _Hold


def _app(name: str, label: str = "") -> App:
    return App(name, label or name, lambda **_: nu.Noop())


def _snippet(name: str, source: str = "") -> Snippet:
    return Snippet(name, name, source or name)


def _env(label: str):
    return lambda *args: Env(label=label)


class _Point:
    """An entry point: a name, and what loading it gives."""

    def __init__(self, name: str, load) -> None:
        self.name = name
        self._load = load

    def load(self):
        return self._load()


def _points(monkeypatch, points: list[_Point]) -> list[str]:
    asked: list[str] = []

    def entry_points(*, group: str):
        asked.append(group)
        return points

    monkeypatch.setattr(registry_module, "entry_points", entry_points)
    return asked


# --- the registry ----------------------------------------------------------------


def test_merge_keeps_the_first_per_name_and_warns():
    first = Extension((_app("page", "Mine"),), (_snippet("prose", "a"),), {"db": _env("mine")}, "a")
    second = Extension(
        (_app("page", "Theirs"), _app("job")),
        (_snippet("prose", "b"), _snippet("heading")),
        {"db": _env("theirs"), "llm": _env("llm")},
        "b",
    )
    with pytest.warns(RegistryWarning) as caught:
        reg = Registry.merge([first, second])
    assert len(caught) == 3
    assert "'page' from b ignored: a registered it first" in str(caught[0].message)
    assert list(reg.apps) == ["page", "job"]
    assert reg.apps["page"].label == "Mine"
    assert reg.snippets["prose"].source == "a"
    assert list(reg.snippets) == ["prose", "heading"]
    assert reg.envs["db"]().label == "mine"
    assert set(reg.envs) == {"db", "llm"}


def test_discover_loads_extensions_and_factories_and_skips_the_broken(monkeypatch):
    def broken():
        raise ImportError("no such module")

    ext = Extension(apps=(_app("page"),))
    asked = _points(
        monkeypatch,
        [
            _Point("plain", lambda: ext),
            _Point("factory", lambda: lambda: Extension(snippets=(_snippet("prose"),))),
            _Point("broken", broken),
            _Point("wrong", lambda: lambda: 42),
        ],
    )
    with pytest.warns(RegistryWarning) as caught:
        found = discover()
    assert asked == [GROUP]
    assert [e.name for e in found] == ["plain", "factory"]
    assert found[0].apps == ext.apps
    assert [s.name for s in found[1].snippets] == ["prose"]
    said = [str(w.message) for w in caught]
    assert any("'broken' failed to load" in s for s in said)
    assert any("'wrong' is not an Extension: int" in s for s in said)


def test_explicit_wins_over_discovered(monkeypatch):
    installed = Extension((_app("page", "Installed"), _app("job")), (), {"db": _env("installed")})
    _points(monkeypatch, [_Point("nuverse", lambda: installed)])
    mine = Extension((_app("chat"),), (), {}, name="mine")
    with pytest.warns(RegistryWarning) as caught:
        reg = space_registry(
            apps=[_app("page", "Loose")], envs={"db": _env("loose")}, extensions=[mine]
        )
    assert {str(w.message) for w in caught} == {
        "app 'page' from nuverse ignored: open_space registered it first",
        "env 'db' from nuverse ignored: open_space registered it first",
    }
    assert list(reg.apps) == ["page", "chat", "job"]
    assert reg.apps["page"].label == "Loose"
    assert reg.envs["db"]().label == "loose"


def test_discovery_can_be_turned_off(monkeypatch):
    asked = _points(monkeypatch, [_Point("nuverse", lambda: Extension((_app("page"),)))])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        reg = space_registry(snippets=[_snippet("prose")], discover=False)
    assert asked == []
    assert (list(reg.apps), list(reg.snippets)) == ([], ["prose"])


# --- open_space ------------------------------------------------------------------


USER = "user"
TAB = "tab"
STARTER = "starter"


async def test_boot_before_the_first_open_keeps_the_services(store):
    await store.run(boot(USER) >> ensure_system())
    assert await store.read(ops.cell_rows(init.PLANE)) == [
        {"id": "main", "name": "main", "prog": init.SHIM, "meta": {}}
    ]
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert (rows[init.PLANE]["name"], rows[init.PLANE]["system"]) == (init.PLANE, True)
    boot_list = reroot(init.Boot.planes, init.PLANE, init.CELL)
    assert await store.read(nu.list(boot_list)) == [*BOOTED, USER]


async def test_open_space_headless_runs_a_booted_plane(tmp_path, monkeypatch):
    """A store seeded the way a person would, boot() before anything opened it."""
    _points(monkeypatch, [])
    path = str(tmp_path / "space")
    seed = ops.add_plane(USER) >> ops.add_cell(USER, SET_42, cell_id="c") >> boot(USER)
    # A tab the previous run never closed, routed to a plane of its own.
    stale = Space.connections["stale"]
    seed = (
        seed
        >> ops.add_plane(TAB)
        >> ops.add_cell(TAB, SET_42, cell_id="c")
        >> atomic(stale.opened.set(nu.Float(0.0)) >> stale.route.set(nu.Str(TAB)))
        # nuverse's starter program runs headless too.
        >> ops.add_plane(STARTER)
        >> ops.add_cell(STARTER, nuverse_program.SOURCE, cell_id="c")
        >> boot(STARTER)
    )
    await nu.arun(nu.With(store(path), body=seed))

    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    held = nu.Let("test.held", _Hold(ready, done), nu.SetCmd(nu.AnyAttrRef("test.x"), 1))
    term = open_space(path, web=False, spares=1, name="nuspace-host", body=held)
    task = asyncio.create_task(nu.arun(term))
    space = Kernel(await asyncio.wait_for(asyncio.shield(ready), 20), done, task)
    try:
        state = Space.planes[USER].cells["c"].state.extract()
        assert await space.until(state, lambda s: s == {"n": 42}) == {"n": 42}
        starter = Space.planes[STARTER].cells["c"].state.extract()
        assert await space.until(starter, lambda s: s == {"hello": "world"}) == {"hello": "world"}
        # The services are made and init brought up its boot list beside the user plane.
        assert {r["id"] for r in await space.read(ops.plane_rows())} >= {
            USER,
            *(plane for plane, _ in SERVICES),
        }
        for plane in BOOTED:
            await space.until(
                ops.runs(plane=plane), lambda rs: any(r["status"] == STATUS_UP for r in rs)
            )
        # Cleared before init started nav: the stale tab brought nothing up.
        assert await space.read(nu.list(Space.connections.keys())) == []
        assert await space.read(ops.runs(plane=TAB)) == []
    finally:
        await space.close()


# --- nuverse's snippets ---------------------------------------------------------


async def test_nuverse_prose_loads_through_the_kernel_rewrites(store):
    """Prose draws, so it runs only in a session: here it is loaded and compiled."""
    from nuspace.system.devices.web.env import session_env

    await store.run(ops.add_plane("p") >> ops.add_cell("p", nuverse_prose.SOURCE, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite, Bracketed())
    source = Space.planes["p"].cells["c"].prog
    term = await store.run(
        nustd.kv.auto_flow_atomic(
            source.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


def test_open_space_with_web_compiles(monkeypatch):
    _points(monkeypatch, [])
    term = open_space(apps=[_app("page")], snippets=[_snippet("prose")], open_browser=False)
    nu.validate(nu.compile(term))


# --- the command line ------------------------------------------------------------


@pytest.mark.parametrize("args", [["--help"], ["serve", "--help"], ["run", "--help"]])
def test_cli_help(args):
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert "Usage" in result.output


def test_importing_nuspace_pulls_in_no_server_and_no_cli():
    code = (
        "import sys, nuspace\n"
        "print(sorted(m for m in ('fastapi', 'uvicorn', 'click', 'nustd.ws_server')"
        " if m in sys.modules))"
    )
    out = subprocess.run(  # noqa: S603 -- our own interpreter, a fixed script
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"
