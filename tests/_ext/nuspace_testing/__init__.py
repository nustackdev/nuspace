"""nuspace's test extension: the specs of ``_support.specs``, installed so every process finds them.

A space registers only what installed packages add, and a worker finds a
content kind by its registered name from the installed entry points. The
dev env installs this package, so the tests' Planes, Cells and kinds
register as ``testing.<name>``: ``testing.plain``, ``testing.text``,
``testing.Note``. It registers nothing unless :data:`ENV` is set, as the
test suite sets it, so a space run from the dev env is left as it is.
"""

from __future__ import annotations

import os

from nuspace import Extension


__all__ = ["ENV", "extension"]


#: Set to register the specs. ``_support`` imports only where it is set.
ENV = "NUSPACE_TESTING"


def extension() -> Extension:
    """The tests' specs, when :data:`ENV` is set. Nothing otherwise."""
    if not os.environ.get(ENV):
        return Extension()
    from _support.specs import CELLS, CONTENTS, PLANES

    return Extension(planes=PLANES, cells=CELLS, contents=CONTENTS)
