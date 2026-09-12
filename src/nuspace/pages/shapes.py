"""Pages store layout, plus the runner's host-local bookkeeping.

``Page`` and ``Section`` are what the store holds; ``Runner`` is what the
process driving one page knows. This module imports nothing from
:mod:`nuspace.core`, which is what keeps ``core.shapes`` -> ``pages.shapes``
a one-way edge.
"""

from __future__ import annotations

import nu
import nu.kv
import nu.mem
from nuspace.recursive import RecursiveShape, self_slot


__all__ = ["DEFAULT_POLICY", "ORDER_STEP", "Page", "Runner", "Section"]


#: What a section runs under when nobody said otherwise. For v1 nothing reads it.
DEFAULT_POLICY = "always"

#: Gap between neighbours after a renormalise, so one can be dropped between
#: two others later without touching either.
ORDER_STEP = 10


class Section(nu.Shape):
    """One block on a page, and the unit of execution. Always a Nu program.

    ``snippet`` is a ``nu.prog`` program: a module with an ``out`` entry point
    whose signature is the scope contract, and nuspace binds one value,
    ``path``, which for a section is ``"sections.<section_id>"``.
    """

    # Section ids are globally unique, not unique per page: `path` is the only
    # thing a snippet's scope carries, so two pages reusing an id would share
    # one namespace. See nuspace.core.tpl.
    name = nu.kv.StrRef.slot()
    snippet = nu.kv.ProgramRef.slot()
    policy = nu.kv.StrRef.slot()
    # `tpl` is provenance, not type. It says what produced the snippet and
    # nothing branches on it to decide whether a block runs. See core.tpl.
    tpl = nu.kv.StrRef.slot()
    # Sections sort by their creation-ordered id until someone drags one;
    # `order` is what makes reordering expressible. ops renormalises it.
    order = nu.kv.IntRef.slot()


class Page(RecursiveShape):
    """A page: a title, a bag of sections, and nested child pages.

    ``pages`` holds ``Page`` itself, which a class body cannot name, so it is
    declared with ``self_slot``. A page is a container; the sections on it are
    what actually run.
    """

    title = nu.kv.StrRef.slot()
    sections = nu.kv.ShapesDictRef.slot(Section)
    pages = self_slot(nu.kv.ShapesDictRef)


class Runner(nu.Shape):
    """What the process driving one page knows about who is running what.

    ``nu.mem`` deliberately: this is host-local bookkeeping, and a kv write
    here would let the driver wake itself. Keyed by section id, so a preset
    running two views at once gives each its own ``dict`` binding.
    """

    workers = nu.mem.DictRef.slot(int)
