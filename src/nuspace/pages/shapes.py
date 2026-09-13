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


__all__ = [
    "DEFAULT_POLICY",
    "ROOT_PAGE_ID",
    "ROOT_PARENT",
    "ROOT_TITLE",
    "WORKER_SLOT",
    "Page",
    "Runner",
    "Section",
]


#: What a section runs under when nobody said otherwise. For v1 nothing reads it.
DEFAULT_POLICY = "always"

#: Key of the one page every other page descends from. Fixed rather than
#: minted, so a cold store and a browser route can both name it without
#: reading anything first. ``ops.init_space`` writes it.
ROOT_PAGE_ID = "root"

#: The root page is its own parent. Every ``parent`` is therefore a real page
#: key, so ``pages[page.parent]`` is always addressable and no op needs a
#: special case for the top of the tree.
ROOT_PARENT = ROOT_PAGE_ID

#: What the root page is called when ``init_space`` is not told otherwise.
ROOT_TITLE = "Home"


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


class Page(nu.Shape):
    """A page: a title, its place in the tree, and a bag of sections.

    Pages live in one flat dict on ``Space``, so ``parent`` and ``children``
    are ordinary data and a page is addressed by id at a fixed depth.
    """

    title = nu.kv.StrRef.slot()
    # Two facts that must agree, which is why ops is the only writer: every
    # structural op fixes both sides in one tree. The root page parents
    # itself, so this is never empty and never names a page that is not there.
    parent = nu.kv.StrRef.slot()
    children = nu.kv.ListRef.slot(str)
    sections = nu.kv.ShapesDictRef.slot(Section)
    # List position is the order. No `order` field, nothing to renormalise.
    section_order = nu.kv.ListRef.slot(str)


class Runner(nu.Shape):
    """What the process driving one page knows about who is running it.

    One slot, because a page is the unit: every section on it folds into a
    single worker, so a view is either running somewhere or it is not.
    ``nu.mem`` deliberately -- this is host-local bookkeeping, and a kv write
    here would let the driver wake itself. A preset running two views at once
    gives each its own ``dict`` binding.
    """

    worker = nu.mem.IntRef.slot()


#: The key ``Runner.worker`` occupies in the dict backing it. Declared beside
#: the slot so a bracket owning that dict can reach the record without a ref.
WORKER_SLOT = "worker"
