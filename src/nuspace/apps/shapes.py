"""Apps store layout, plus the runner's host-local bookkeeping.

``App`` is what the store holds; ``Runner`` is what the host process knows.
This module imports nothing from :mod:`nuspace.core`, which is what keeps
``core.shapes`` -> ``apps.shapes`` a one-way edge.
"""

from __future__ import annotations

import nu
import nu.kv
import nu.mem


__all__ = ["DEFAULT_POLICY", "App", "Runner"]


#: What an app runs under when nobody said otherwise. For v1 nothing reads it.
DEFAULT_POLICY = "always"


class App(nu.Shape):
    """One ops-orchestration unit. Same substance as a ``Section``.

    ``snippet`` is a ``nu.prog`` program: a module with an ``out`` entry point
    whose signature is the scope contract, and nuspace binds two ids, ``page``
    and ``section``. An app is a section with no page, so ``section`` is its
    own id and ``page`` is empty.
    """

    # An app is headless -- it produces, a page displays -- so nothing roots
    # the refs it names and it has nowhere to render.
    name = nu.kv.StrRef.slot()
    snippet = nu.kv.ProgramRef.slot()
    # Metadata. The policy engine slots in behind this, not beside it.
    policy = nu.kv.StrRef.slot()


class Runner(nu.Shape):
    """What the host process knows about who is running what.

    ``nu.mem`` deliberately: this is host-local bookkeeping, and a kv write
    here would let the driver wake itself. Pool ids are never reused, so "the
    worker id changed" is a sound test for "that app restarted".
    """

    workers = nu.mem.DictRef.slot(int)
    # Written by the runner's boot pass and by nothing else. Mem, so it reads
    # True only where the runner itself is: a web driver in the same process
    # sees it, one in another process never can, and neither has to be told.
    attached = nu.mem.BoolRef.slot()
