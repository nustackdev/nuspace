"""Packaging: nuverse installed beside nuspace, found the way a third party is.

nuspace never imports nuverse. These check the entry point finds it, what it
registers is well formed, and importing it keeps a worker light.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path

import nu
import nuverse
from nuspace import App, Extension, Snippet
from nuspace.host import discover, space_registry
from nuverse import apps, snippets


ROOT = Path(__file__).parents[2]


def _run(code: str) -> str:
    out = subprocess.run(  # noqa: S603 -- our own interpreter, a fixed script
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=ROOT,
        check=True,
    )
    return out.stdout.strip()


def _nuverse() -> Extension:
    (ext,) = [e for e in discover() if e.name == "nuverse"]
    return ext


def test_discovery_finds_nuverse():
    ext = _nuverse()
    assert ext == replace(nuverse.extension(), name="nuverse")
    assert [a.name for a in ext.apps] == ["page", "runs", "workers", "planes"]
    assert [s.name for s in ext.snippets] == ["prose", "program", "ticker"]
    assert dict(ext.envs) == {}


def test_open_space_registers_nuverse_by_default():
    reg = space_registry()
    assert {"page"} <= set(reg.apps)
    assert {"prose", "program", "ticker"} <= set(reg.snippets)
    assert space_registry(discover=False).apps == {}


def test_apps_are_well_formed():
    assert apps.APPS == (apps.page.APP, apps.runs.APP, apps.workers.APP, apps.planes.APP)
    # Placeholders are left out until they are filled in.
    assert (apps.job.APP, apps.chat.APP) == (None, None)
    for app in apps.APPS:
        assert isinstance(app, App)
        assert app.name and app.label
        assert isinstance(app.build(plane_id="p", name="P"), nu.Nu)
    assert len({a.name for a in apps.APPS}) == len(apps.APPS)


def test_snippets_are_well_formed():
    assert snippets.SNIPPETS == (
        snippets.prose.SNIPPET,
        snippets.program.SNIPPET,
        snippets.ticker.SNIPPET,
    )
    assert (snippets.heading.SNIPPET, snippets.monaco.SNIPPET) == (None, None)
    for snippet in snippets.SNIPPETS:
        assert isinstance(snippet, Snippet)
        assert snippet.name and snippet.label
        namespace: dict = {}
        exec(compile(snippet.source, snippet.name, "exec"), namespace)  # noqa: S102
        assert callable(namespace["out"])
        assert isinstance(namespace["out"](), nu.Nu)
    assert len({s.name for s in snippets.SNIPPETS}) == len(snippets.SNIPPETS)


def test_importing_nuverse_loads_no_server():
    heavy = _run(
        """
        import sys
        import nuverse
        nuverse.extension()
        print(sorted(
            m for m in sys.modules
            if m.split(".")[0] in ("fastapi", "uvicorn", "starlette") or m == "nustd.ws_server"
        ))
        """
    )
    assert heavy == "[]"


def test_example_defines_nothing_of_its_own():
    """The example registers no apps or snippets: nuverse is found on install."""
    out = _run(
        """
        import runpy
        space = runpy.run_path("examples/space.py")
        from nuspace.host import space_registry
        reg = space_registry()
        print("APPS" in space, "SNIPPETS" in space, sorted(reg.apps), sorted(reg.snippets))
        """
    )
    assert out.startswith("False False ['page', 'planes', 'runs', 'workers']")
