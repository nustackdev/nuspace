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
import nu.proxy
from nu.ui.core import Session
from nuspace._root import resolve_root
from nuspace.core.fields import MountFields
from nuspace.core.host import spare_observer
from nuspace.core.session import FrameCodec

from .shapes import Runner


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "CHANGED_SECTION_INDEX",
    "SECTION_ATTR",
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


#: What a reconcile pass binds the section it is about under, and the attr
#: ``carry=True`` ships into the worker. Overridable per caller: two passes
#: that can run at once share one ``ctx.attrs`` and so may not share a name.
SECTION_ATTR = "section"

#: The key that woke the live loop, and the section id inside it.
_KEY = nu.TupleAttrRef("k")
changed_section = _KEY[CHANGED_SECTION_INDEX]


def _worker_attr(item: str) -> str:
    """Where a pass working on ``item`` parks the worker it just launched.

    Derived from ``item`` for the reason ``item`` itself is overridable: two
    passes that can run at once share one ``ctx.attrs``.
    """
    return f"{item}.w"


def _term_attr(item: str) -> str:
    """Where a pass working on ``item`` parks the term it just constructed."""
    return f"{item}.t"


def section_body(
    page_id: nu.StrArg,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    item: str = SECTION_ATTR,
) -> nu.Nu:
    """One section running, as the single term every ``Dispatch`` ships.

    One per page, not one per section: a ``Dispatch`` body is payload, so it is
    fixed at construction and the section arrives as the carried attr ``item``.

    Args:
        page_id: the page the section is on.
        session_address: where this connection's ``nu.ui`` Session is served.
            The proxy is opened here rather than in ``worker_init`` because a
            pool is process-wide and fixes its init once, while the Session is
            one browser connection and every connection has an address of its
            own. None runs the page headless: no Session is served, so a
            snippet naming a ui ref fails to find one.
        root: the space's root Shape class.
        item: the attr the section id is bound under.
    """
    root = resolve_root(root)
    section = nu.StrAttrRef(item)
    sections = root.pages[page_id].sections
    # `path` in the snippet's scope is the section's kv namespace, keyed by
    # section id alone -- never the page id. See nuspace.core.tpl.
    prefix = nu.Str("sections.") + section
    load = sections[section].snippet.load(scope={"path": prefix})
    term_attr = _term_attr(item)
    term = nu.AnyAttrRef(term_attr)
    # Enumerated here, in the worker, because this is the process that builds
    # the term: the fields are what the snippet actually named, not what the
    # editor guessed. Written before the Eval, which never returns.
    publish = nu.kv.auto_flow_atomic(
        root.state.set_item(prefix + nu.Str(".fields"), MountFields(term, prefix)),
        scope=root,
    )
    # Construction failures are written to the section's namespace, not
    # raised: a dispatched body has no waiter, so an error vanishes silently.
    report = nu.kv.auto_flow_atomic(
        root.state.set_item(prefix + nu.Str(".error"), nu.ToStr(nu.AttrRef("error"))),
        scope=root,
    )
    run = nu.Let(
        term_attr,
        nu.kv.auto_flow_atomic(load, scope=root),
        # ParallelAsync over the one Eval, which is how a term says "on the
        # loop". Every nu.ui atom is async-only and an Eval placed off the
        # loop refuses to host one, so a section that renders has nowhere
        # else to run.
        body=publish >> nu.ParallelAsync(nu.prog.Eval(term)),
    )
    # The observer sits here rather than in ``worker_init``: a snippet with a
    # kv subscription needs one bound, and a pool whose every worker pays for
    # it on the way up makes a restart slow enough to see.
    guarded = nu.With(
        spare_observer(),
        body=nu.TryCatch(run, catch=report, errors=nu.prog.ConstructionError),
    )
    if session_address is None:
        return guarded
    return nu.With(
        # Frames are the one thing that crosses back, and invisibles ships an
        # unknown class by reference rather than by value.
        nu.Provide(FrameCodec, {}),
        # Every nu.ui Ref the snippet builds asks ctx for a Session, and this
        # is the one the browser is on the other end of. bg_serve, because a
        # subscription's callback is a reverse proxy the server calls back.
        nu.proxy.InvisiblesProxy(Session, address=session_address, bg_serve=True),
        body=guarded,
    )


def reconcile(
    page_id: nu.StrArg,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    body: nu.Nu | None = None,
    item: str = SECTION_ATTR,
) -> nu.Nu:
    """Make the world agree with the store, for the one section bound at ``item``.

    One path for add, edit and delete: whatever is running for this section
    stops, and if the page still has the section it starts again. The pool
    comes off the ambient context, which is what lets a preset decide where
    sections execute.

    Args:
        page_id: the page whose sections this reconciles.
        session_address: where this connection's Session is served. None runs
            the page headless. See :func:`section_body`.
        root: the space's root Shape class.
        body: the term to dispatch. Defaults to :func:`section_body`; replace
            it to run a section somewhere other than a pool worker.
        item: the attr the section id is bound under. Whoever binds it must
            use the same name, and two passes that can run at once must not
            share one.
    """
    root = resolve_root(root)
    section = nu.StrAttrRef(item)
    worker_attr = _worker_attr(item)
    worker = nu.IntAttrRef(worker_attr)
    sections = root.pages[page_id].sections
    pool = nu.mp_pool.PoolRef()
    stop = nu.IfDo(
        Runner.workers.contains(section),
        pool.kill(Runner.workers[section]) >> Runner.workers.del_item(section),
    )
    start = nu.IfDo(
        # A section that has been deleted reaches here too -- that is the
        # delete path, and this is what stops it coming back.
        sections.contains(section),
        # The worker id is read twice, recorded and then dispatched to, so it
        # is bound once and scoped to the two reads that want it.
        nu.Let(
            worker_attr,
            pool.launch(),
            body=Runner.workers.set_item(section, worker)
            >> pool.dispatch(
                section_body(page_id, session_address=session_address, root=root, item=item)
                if body is None
                else body,
                worker,
                carry=True,
            ),
        ),
    )
    return stop >> start


def page_driver(
    page_id: nu.StrArg,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    body: nu.Nu | None = None,
    item: str = SECTION_ATTR,
) -> tuple[nu.Nu, nu.Nu]:
    """The seed pass and the live loop for one page, as two terms.

    Returned separately because they compose differently: the seed must finish
    before anything else starts, and the live loop never finishes at all.
    """
    root = resolve_root(root)
    sections = root.pages[page_id].sections
    pass_ = reconcile(page_id, session_address=session_address, root=root, body=body, item=item)
    # Both containers must exist before anything reads them: a subscription
    # over a missing container resolves to INVALID and silently never fires.
    # Dict.create(), not {} -- a literal dict is captured once at Form
    # construction and shared across every evaluation of the term.
    boot = sections.init(nu.Dict.create()) >> Runner.workers.init(nu.Dict.create())
    # nu.list is load-bearing: the keys view is lazy and auto_flow_atomic
    # brackets the items slot separately, so an undrained view outlives its
    # Snapshot and dies with StorageClosedError.
    seed = boot >> nu.ForEachDo(nu.list(sections.keys()), pass_, item=item)
    # The bare key naming no section also fires. It must be skipped
    # explicitly: indexing past the end raises IndexError inside the react
    # loop, killing it and leaving the runner silently deaf.
    live = nu.ReactForever(
        sections.on_change(),
        nu.IfDo(
            nu.Len(_KEY) > nu.Int(CHANGED_SECTION_INDEX),
            # Same binding the seed pass makes with ForEachDo, and scoped the
            # same way, so no reaction leaves one behind.
            nu.Let(item, changed_section, body=pass_),
        ),
        changed_key="k",
    )
    return seed, live


def page_tree(
    page_id: nu.StrArg,
    *,
    session_address: str | None = None,
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
        session_address: where this connection's Session is served. See
            :func:`reconcile`.
        root: the space's root Shape class.
        body: the term dispatched per section. See :func:`reconcile`.
        alongside: a tree to run beside the live loop, for demos and tests.
        duration: stop after this many seconds. None runs forever.

    Returns:
        The tree, already bracketed for atomicity against ``root``.
    """
    root = resolve_root(root)
    seed, live = page_driver(page_id, session_address=session_address, root=root, body=body)
    flow = live if alongside is None else (live | alongside)
    if duration is not None:
        flow = nu.Race(flow, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    return nu.kv.auto_flow_atomic(seed >> flow, scope=root)
