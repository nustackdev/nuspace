"""Every entry into the package imports, from a cold interpreter.

``core.shapes`` needs ``App`` from ``apps.shapes`` while ``apps.ops`` needs
``Space`` from ``core.shapes``, so the import order in ``nuspace/__init__`` is
load-bearing and this is what says so out loud.
"""

from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    ["nuspace", "nuspace.apps", "nuspace.apps.ops", "nuspace.core", "nuspace.core.shapes"],
)
def test_a_cold_interpreter_can_import(module):
    subprocess.run([sys.executable, "-c", f"import {module}"], check=True)  # noqa: S603
