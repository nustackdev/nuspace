"""The page driver: every section on one page, running, as one Nu tree.

Not a host. ``apps/runner.py`` owns the store, the pool and the process and
runs forever; a page runs per view, so this builds the tree for one page out
of the context it is handed and something else -- a preset -- mounts it, owns
the ``With`` head and decides how long it lives.

Same reactive shape as apps otherwise: seed the sections already on the page,
then react to the page's own sections forever, with a single reconcile path
covering add, edit and delete.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mp_pool
import nu.prog
from nuspace._root import resolve_root

from .shapes import Runner


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "CHANGED_SECTION_INDEX",
    "changed_section",
    "page_driver",
    "page_tree",
    "reconcile",
    "section_body",
]


#: Position of the section id in a key from ``page.sections.on_change()``.
#: Pages are flat, so a key is always ``('/', 'pages', page_id, 'sections',
#: section_id)`` with an optional field after it, and index 4 reaches the id
#: whatever the page's depth in the tree. Measured, and pinned by
#: ``tests/nuspace/pages/test_changed_key.py``.
CHANGED_SECTION_INDEX = 4


#: The section a reconcile pass is about, carried into the worker by ``carry=True``.
_SECTION = nu.StrAttrRef("section")

#: The key that woke the live loop, and the section id inside it.
_KEY = nu.TupleAttrRef("k")
changed_section = _KEY[CHANGED_SECTION_INDEX]


def section_body(page_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """One section running, as the single term every ``Dispatch`` ships.

    One per page, not one per section: a ``Dispatch`` body is payload, so it
    is fixed at construction and the section arrives as the carried attr
    ``section``.
    """
    root = resolve_root(root)
    sections = root.pages[page_id].sections
    # `path` in the snippet's scope is the section's kv namespace, keyed by
    # section id alone -- never the page id. See nuspace.core.tpl.
    scope = {"path": nu.Str("sections.") + _SECTION}
    load = sections[_SECTION].snippet.load(scope=scope)
    # Construction failures are written to the section's namespace, not
    # raised: a dispatched body has no waiter, so an error vanishes silently.
    report = nu.kv.auto_flow_atomic(
        root.state.set_item(
            nu.Str("sections.") + _SECTION + nu.Str(".error"), nu.ToStr(nu.AttrRef("error"))
        ),
        scope=root,
    )
    return nu.TryCatch(
        nu.prog.Eval(nu.kv.auto_flow_atomic(load, scope=root)),
        catch=report,
        errors=nu.prog.ConstructionError,
    )


def reconcile(
    page_id: nu.StrArg, *, root: type[Shape] | None = None, body: nu.Nu | None = None
) -> nu.Nu:
    """Make the world agree with the store, for the one section bound at ``section``.

    Kill whatever worker is on record, then start whatever the store says the
    section is now: an add runs the second half, a delete the first, an edit
    both. The pool comes off the ambient context rather than being owned here,
    which is what lets a preset decide where sections execute.

    Args:
        page_id: the page whose sections this reconciles.
        root: the space's root Shape class.
        body: the term to dispatch. Defaults to :func:`section_body`; replace
            it to run a section somewhere other than a pool worker.
    """
    root = resolve_root(root)
    sections = root.pages[page_id].sections
    pool = nu.mp_pool.PoolRef()
    stop = nu.IfDo(
        Runner.workers.contains(_SECTION),
        pool.kill(Runner.workers[_SECTION]) >> Runner.workers.del_item(_SECTION),
    )
    start = nu.IfDo(
        sections.contains(_SECTION),
        nu.SetCmd(nu.AttrRef("w"), pool.launch())
        >> Runner.workers.set_item(_SECTION, nu.AttrRef("w"))
        >> pool.dispatch(
            section_body(page_id, root=root) if body is None else body,
            nu.AttrRef("w"),
            carry=True,
        ),
    )
    return stop >> start


def page_driver(
    page_id: nu.StrArg, *, root: type[Shape] | None = None, body: nu.Nu | None = None
) -> tuple[nu.Nu, nu.Nu]:
    """The seed pass and the live loop for one page, as two terms.

    Returned separately because they compose differently: the seed must finish
    before anything else starts, and the live loop never finishes at all.
    """
    root = resolve_root(root)
    sections = root.pages[page_id].sections
    pass_ = reconcile(page_id, root=root, body=body)
    # Both containers must exist before anything reads them: a subscription
    # over a missing container resolves to INVALID and silently never fires.
    # Dict.create(), not {} -- a literal dict is captured once at Form
    # construction and shared across every evaluation of the term.
    boot = sections.init(nu.Dict.create()) >> Runner.workers.init(nu.Dict.create())
    # nu.list is load-bearing: the keys view is lazy and auto_flow_atomic
    # brackets the items slot separately, so an undrained view outlives its
    # Snapshot and dies with StorageClosedError.
    seed = boot >> nu.ForEachDo(nu.list(sections.keys()), pass_, item="section")
    # The bare key naming no section also fires. It must be skipped
    # explicitly: indexing past the end raises IndexError inside the react
    # loop, killing it and leaving the runner silently deaf.
    live = nu.ReactForever(
        sections.on_change(),
        nu.IfDo(
            nu.Len(_KEY) > nu.Int(CHANGED_SECTION_INDEX),
            nu.SetCmd(_SECTION, changed_section) >> pass_,
        ),
        changed_key="k",
    )
    return seed, live


def page_tree(
    page_id: nu.StrArg,
    *,
    root: type[Shape] | None = None,
    body: nu.Nu | None = None,
    alongside: nu.Nu | None = None,
    duration: float | None = None,
) -> nu.Nu:
    """One page, running, as one term for whoever is mounting it.

    No ``With`` head: the store, the pool and the ``dict`` behind
    ``Runner.workers`` all come from the context this is run in, so a preset
    can give each view its own without this module knowing about views.

    Args:
        page_id: the page to run.
        root: the space's root Shape class.
        body: the term dispatched per section. See :func:`reconcile`.
        alongside: a tree to run beside the live loop, for demos and tests.
        duration: stop after this many seconds. None runs forever.

    Returns:
        The tree, already bracketed for atomicity against ``root``.
    """
    root = resolve_root(root)
    seed, live = page_driver(page_id, root=root, body=body)
    flow = live if alongside is None else (live | alongside)
    if duration is not None:
        flow = nu.Race(flow, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    return nu.kv.auto_flow_atomic(seed >> flow, scope=root)
