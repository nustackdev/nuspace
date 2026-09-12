"""No entry into the package depends on which module is imported first.

``core.shapes`` needs ``App`` and ``Page`` from the submodule shapes, and the
submodule ops and runners need ``Space`` from ``core.shapes``. The second half
of that is deferred to call time, so the edge ``core.shapes -> {apps,pages}
.shapes`` is one-way and every order below has to work. These tests are what
says so out loud: they would have failed for ``pages`` under the old
import-order fix, which only ever worked because ``apps`` sorts before
``core``.
"""

from __future__ import annotations

import itertools
import subprocess
import sys

import pytest


MODULES = [
    "nuspace",
    "nuspace._root",
    "nuspace.apps",
    "nuspace.apps.ops",
    "nuspace.apps.runner",
    "nuspace.apps.shapes",
    "nuspace.core",
    "nuspace.core.ids",
    "nuspace.core.shapes",
    "nuspace.core.tpl",
    "nuspace.pages",
    "nuspace.pages.ops",
    "nuspace.pages.runner",
    "nuspace.pages.shapes",
    "nuspace.web",
    "nuspace.web.apps",
    "nuspace.web.apps.driver",
    "nuspace.web.apps.ref",
    "nuspace.web.arms",
    "nuspace.web.nav",
    "nuspace.web.pages",
    "nuspace.web.pages.driver",
    "nuspace.web.pages.ref",
    "nuspace.web.serve",
    "nuspace.web.serve.app",
    "nuspace.web.serve.fabric",
    "nuspace.web.serve.session",
    "nuspace.web.serve.shell",
    "nuspace.web.space",
    "nuspace.web.wire",
]

#: One module per package entry point, to pair up. Every ordering of these is
#: tried, which is the property the old ordering comment could not offer.
ENTRIES = ["nuspace.apps.ops", "nuspace.core.shapes", "nuspace.pages.ops", "nuspace.pages.runner"]


def _cold(*modules):
    """Import ``modules`` in that order in a fresh interpreter."""
    script = "\n".join(f"import {m}" for m in modules)
    subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603


@pytest.mark.parametrize("module", MODULES)
def test_a_cold_interpreter_can_import(module):
    _cold(module)


@pytest.mark.parametrize("first,second", list(itertools.permutations(ENTRIES, 2)))
def test_neither_of_two_entries_has_to_come_first(first, second):
    _cold(first, second)


def test_the_root_helper_resolves_the_stock_space():
    from nuspace._root import resolve_root
    from nuspace.core.shapes import Space

    assert resolve_root(None) is Space
    assert resolve_root(Space) is Space


def test_no_ops_or_runner_module_names_space_at_import_time():
    """The source check behind the property, so a regression names itself."""
    from pathlib import Path

    import nuspace

    root = Path(nuspace.__file__).parent
    for name in ("apps/ops.py", "apps/runner.py", "pages/ops.py", "pages/runner.py"):
        source = (root / name).read_text()
        top = source.split("if TYPE_CHECKING:")[0]
        assert "from nuspace.core.shapes import" not in top, name
