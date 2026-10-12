"""Packaging: nuspace stands alone, every Plane and snippet comes from an extension.

nuspace ships none of its own. These check a bare install registers nothing,
and the example leaves it all to what is installed.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from nuspace.host import discover, space_registry


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


def test_a_bare_install_registers_nothing():
    assert discover() == []
    reg = space_registry()
    assert (reg.planes, reg.snippets) == ({}, {})


def test_example_defines_nothing_of_its_own():
    """The example registers no Planes or snippets: they come from extensions."""
    out = _run(
        """
        import runpy
        space = runpy.run_path("examples/space.py")
        print("PLANES" in space, "SNIPPETS" in space)
        """
    )
    assert out == "False False"
