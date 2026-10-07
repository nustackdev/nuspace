"""nuverse's snippet and plane packages import nothing until asked.

A cell's prog imports one snippet or one plane module. When importing the
package pulled in every sibling with it, two cells loading on two threads met
inside the package's ``__init__`` and the import system raised a deadlock.
"""

from __future__ import annotations

import subprocess
import sys


def _loaded(code: str) -> list[str]:
    script = (
        "import sys\n"
        f"{code}\n"
        "print(sorted(m for m in sys.modules"
        " if m.startswith(('nuverse.snippets.', 'nuverse.planes.'))))\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=True
    )
    return eval(done.stdout)  # noqa: S307 -- our own print of a list of names


def test_importing_the_packages_loads_no_member():
    assert _loaded("import nuverse.snippets, nuverse.planes") == []


def test_a_cell_prog_loads_only_its_own_snippet():
    loaded = _loaded("from nuverse.snippets.table import snippet")
    assert not [m for m in loaded if m.startswith("nuverse.snippets.prose")]


def test_the_registries_load_every_member_in_order():
    from nuverse.planes import PLANES
    from nuverse.snippets import SNIPPETS

    assert [s.name for s in SNIPPETS][:3] == ["text", "table", "text_input"]
    assert PLANES[0].name == "plain"
