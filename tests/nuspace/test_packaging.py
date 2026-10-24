"""Packaging: nuspace stands alone, every Plane and Cell comes from an extension.

nuspace ships none of its own. These check nuspace registers nothing itself,
and the example leaves it all to what is installed.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from importlib.metadata import entry_points
from pathlib import Path

from nuspace.ext import GROUP, space_registry


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
    """Whatever is discovered comes from another distribution, eg the demos extra."""
    assert not [p for p in entry_points(group=GROUP) if p.dist and p.dist.name == "nuspace"]
    reg = space_registry(discover=False)
    assert (reg.planes, reg.cells) == ({}, {})


def test_example_defines_nothing_of_its_own():
    """The example registers no Planes or Cells: they come from extensions."""
    out = _run(
        """
        import runpy
        space = runpy.run_path("examples/space.py")
        print("PLANES" in space, "CELLS" in space)
        """
    )
    assert out == "False False"
