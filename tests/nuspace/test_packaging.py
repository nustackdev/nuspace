"""Packaging: nuverse installed beside nuspace, found the way a third party is.

nuspace never imports nuverse. These check the entry point finds it, what it
registers is well formed, and importing it keeps a worker light.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import textwrap
from dataclasses import replace
from pathlib import Path

import nu
import nuverse
from nuspace import Extension, Plane, Snippet
from nuspace.host import discover, space_registry
from nuverse import planes, snippets


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
    assert [p.name for p in ext.planes] == ["plain", "jobs", "runs", "workers", "planes"]
    assert [s.name for s in ext.snippets] == [
        "prose",
        "program",
        "ticker",
        "lens",
        "plane_lens",
        "cell_lens",
    ]
    assert dict(ext.envs) == {}


def test_open_space_registers_nuverse_by_default():
    reg = space_registry()
    assert next(iter(reg.planes)) == "plain"
    assert {"prose", "program", "ticker"} <= set(reg.snippets)
    assert space_registry(discover=False).planes == {}


def test_planes_are_well_formed():
    assert planes.PLANES == (
        planes.plain.PLANE,
        planes.jobs.PLANE,
        planes.runs.PLANE,
        planes.workers.PLANE,
        planes.planes.PLANE,
    )
    plain = planes.plain.PLANE
    assert (plain.label, plain.cells, plain.children) == ("Plain", (), ())
    for plane in planes.PLANES:
        assert isinstance(plane, Plane)
        assert plane.name and plane.label and plane.description
        assert plane.meta == {"editable": True, "full_width": False}
        for name, source in plane.cells:
            assert name and "def out():" in source
    assert len({p.name for p in planes.PLANES}) == len(planes.PLANES)


def test_snippets_are_well_formed():
    assert snippets.SNIPPETS == (
        snippets.prose.SNIPPET,
        snippets.program.SNIPPET,
        snippets.ticker.SNIPPET,
        snippets.lens.SNIPPET,
        snippets.plane_lens.SNIPPET,
        snippets.cell_lens.SNIPPET,
    )
    assert (snippets.heading.SNIPPET, snippets.monaco.SNIPPET) == (None, None)
    # Typing into an empty line starts a text cell, and nothing else claims it.
    assert [s.name for s in snippets.SNIPPETS if s.on_type] == ["prose"]
    for snippet in snippets.SNIPPETS:
        assert isinstance(snippet, Snippet)
        assert snippet.name and snippet.label
        namespace: dict = {}
        exec(compile(snippet.source, snippet.name, "exec"), namespace)  # noqa: S102
        out = namespace["out"]
        assert callable(out)
        # The kernel offers plane and cell by name; out takes the ones it names.
        offered = {"plane": "p", "cell": "c"}
        wanted = {k: v for k, v in offered.items() if k in inspect.signature(out).parameters}
        assert isinstance(out(**wanted), nu.Nu)
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
    """The example registers no Planes or snippets: nuverse is found on install."""
    out = _run(
        """
        import runpy
        space = runpy.run_path("examples/space.py")
        from nuspace.host import space_registry
        reg = space_registry()
        print("PLANES" in space, "SNIPPETS" in space, sorted(reg.planes), sorted(reg.snippets))
        """
    )
    assert out.startswith("False False ['jobs', 'plain', 'planes', 'runs', 'workers']")
