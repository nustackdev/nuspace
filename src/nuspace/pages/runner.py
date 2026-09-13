"""The page driver: every section on one page, running, in one worker.

Not a host. ``apps/runner.py`` owns the store, the pool and the process and
runs forever; a page runs per view, so this builds the body for one page out
of the context it is handed and something else -- a preset, or the web
session -- launches the worker and decides how long it lives.

A page is the unit, not a section. One worker holds the whole page and every
section on it is an arm of one ``ForEachParAsync``, so the Session proxy and
the observer are paid for once per page rather than once per section. The fold
is built inside the worker because the section list is kv data and the worker
is the process holding the Navigator proxy: it reads its own sections rather
than being handed them.
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
    "page_body",
    "page_tree",
    "run_page",
    "section_arm",
    "stop_page",
]


#: Position of the section id in a key from ``page.sections.on_change()``.
#: Pages are flat, so a key is always ``('/', 'pages', page_id, 'sections',
#: section_id)`` with an optional field after it, and index 4 reaches the id
#: whatever the page's depth in the tree. Measured, and pinned by
#: ``tests/nuspace/pages/test_changed_key.py``.
CHANGED_SECTION_INDEX = 4


#: What the fold binds each section id under, inside the worker. Every arm
#: gets its own Context branch, so one name serves every section and no caller
#: has to namespace it.
SECTION_ATTR = "section"

#: Where an arm parks the term it just constructed. Arm-local for the same
#: reason ``SECTION_ATTR`` is.
_TERM_ATTR = "section.term"

#: The key that woke the live loop, and the section id inside it. Nothing acts
#: on the id any more -- a page is the unit of restart -- but the shape of the
#: key is still what tells a section write from any other page write.
_KEY = nu.TupleAttrRef("k")
changed_section = _KEY[CHANGED_SECTION_INDEX]


def section_arm(
    page_id: nu.StrArg, *, root: type[Shape] | None = None, item: str = SECTION_ATTR
) -> nu.Nu:
    """One section, constructed and running, as one arm of the page's fold.

    The section arrives as the attr ``item``, bound by the fold. Two
    ``TryCatch`` layers, and neither is optional: the fold cancels every
    sibling arm on the first error, so a section that dies has to die alone.

    Args:
        page_id: the page the section is on.
        root: the space's root Shape class.
        item: the attr the fold binds the section id under.
    """
    root = resolve_root(root)
    section = nu.StrAttrRef(item)
    sections = root.pages[page_id].sections
    # `path` in the snippet's scope is the section's kv namespace, keyed by
    # section id alone -- never the page id. See nuspace.core.tpl.
    prefix = nu.Str("sections.") + section
    error_key = prefix + nu.Str(".error")
    load = sections[section].snippet.load(scope={"path": prefix})
    term = nu.AnyAttrRef(_TERM_ATTR)
    # Enumerated here, in the worker, because this is the process that builds
    # the term: the fields are what the snippet actually named, not what the
    # editor guessed. Written before the Eval, which never returns.
    publish = nu.kv.auto_flow_atomic(
        root.state.set_item(prefix + nu.Str(".fields"), MountFields(term, prefix)),
        scope=root,
    )
    # Failures are written to the section's namespace, not raised: a
    # dispatched body has no waiter, so an error would otherwise vanish, and a
    # raise here takes the whole page's fold down with it.
    report = nu.kv.auto_flow_atomic(
        root.state.set_item(error_key, nu.ToStr(nu.AttrRef("error"))),
        scope=root,
    )
    # Last run's error goes before this one starts, or a section that was
    # fixed would still read `failed` off a stale key.
    clear = nu.kv.auto_flow_atomic(
        nu.IfDo(root.state.contains(error_key), root.state.del_item(error_key)),
        scope=root,
    )
    run = nu.Let(
        _TERM_ATTR,
        nu.kv.auto_flow_atomic(load, scope=root),
        # ParallelAsync over the one Eval, which is how a term says "on the
        # loop". Every nu.ui atom is async-only and an Eval placed off the
        # loop refuses to host one, so a section that renders has nowhere
        # else to run.
        body=publish >> nu.ParallelAsync(nu.prog.Eval(term)),
    )
    # Inner catch is construction, outer is everything the running section
    # throws afterwards. Both land on the one `.error` key the browser reads
    # as `failed`, and both end this arm quietly rather than raising into the
    # fold. Nothing retries: the section stays failed until its snippet
    # changes, which restarts the page anyway.
    guarded = nu.TryCatch(run, catch=report, errors=nu.prog.ConstructionError)
    return clear >> nu.TryCatch(guarded, catch=report)


def page_body(
    page_id: nu.StrArg,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    item: str = SECTION_ATTR,
) -> nu.Nu:
    """One whole page running, as the single term the ``Dispatch`` ships.

    The page arrives as a carried attr rather than baked in, because a body is
    payload and one connection navigating around reuses the same one. The
    section list is read here, in the worker, for the same reason the fields
    are: this is the process with the store.

    Args:
        page_id: the page to run.
        session_address: where this connection's ``nu.ui`` Session is served.
            The proxy is opened here rather than in ``worker_init`` because a
            pool is process-wide and fixes its init once, while the Session is
            one browser connection and every connection has an address of its
            own. None runs the page headless: no Session is served, so a
            snippet naming a ui ref fails to find one.
        root: the space's root Shape class.
        item: the attr each arm's section id is bound under.
    """
    root = resolve_root(root)
    sections = root.pages[page_id].sections
    # nu.list is load-bearing: the keys view is lazy and auto_flow_atomic
    # brackets the items slot separately, so an undrained view outlives its
    # Snapshot and dies with StorageClosedError.
    ids = nu.kv.auto_flow_atomic(nu.list(sections.keys()), scope=root)
    # Async-only and never-returning, which is exactly the shape here: every
    # arm is a section that runs until the worker is killed.
    fold = nu.ForEachParAsync(ids, section_arm(page_id, root=root, item=item), item=item)
    # The observer sits here rather than in ``worker_init``: a snippet with a
    # kv subscription needs one bound, and a pool whose every worker pays for
    # it on the way up makes a restart slow enough to see. Once per page now,
    # not once per section.
    guarded = nu.With(spare_observer(), body=fold)
    if session_address is None:
        return guarded
    return nu.With(
        # Frames are the one thing that crosses back, and invisibles ships an
        # unknown class by reference rather than by value.
        nu.Provide(FrameCodec, {}),
        # Every nu.ui Ref the page builds asks ctx for a Session, and this is
        # the one the browser is on the other end of. bg_serve, because a
        # subscription's callback is a reverse proxy the server calls back.
        nu.proxy.InvisiblesProxy(Session, address=session_address, bg_serve=True),
        body=guarded,
    )


def run_page(
    page: nu.Nu,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    body: nu.Nu | None = None,
    ns: str = "page",
) -> nu.Nu:
    """Make this connection run ``page``, whatever it was running before.

    The one restart path, for arriving on a page and for a section on it
    changing alike. The fresh worker is launched and handed the body first and
    the one on record is killed after, so the gap is as short as a launch.

    Args:
        page: the page id, as a term.
        session_address: where this connection's Session is served. None runs
            the page headless. See :func:`page_body`.
        root: the space's root Shape class.
        body: the term to dispatch. Defaults to :func:`page_body`; replace it
            to run a page somewhere other than a pool worker.
        ns: namespaces the attrs this binds. Two arms that can run at once
            share one ``ctx.attrs`` and so may not share a name.
    """
    root = resolve_root(root)
    page_attr, old_attr, new_attr = f"{ns}.p", f"{ns}.old", f"{ns}.new"
    pool = nu.mp_pool.PoolRef()
    started = nu.IntAttrRef(new_attr)
    stopped = nu.IntAttrRef(old_attr)
    dispatch = pool.dispatch(
        page_body(nu.StrAttrRef(page_attr), session_address=session_address, root=root)
        if body is None
        else body,
        started,
        carry=True,
    )
    return nu.Let(
        page_attr,
        page,
        # A slot nothing has written yet reads EMPTY, and EMPTY through a kill
        # is a lookup for a worker that never existed.
        body=nu.Let(
            old_attr,
            nu.If(Runner.worker.not_empty(), Runner.worker, nu.Int(-1)),
            body=nu.Let(
                new_attr,
                pool.launch(),
                body=dispatch
                >> Runner.worker.set(started)
                >> nu.IfDo(stopped >= nu.Int(0), pool.kill(stopped)),
            ),
        ),
    )


def stop_page(*, ns: str = "page") -> nu.Nu:
    """Kill the worker on record, if there is one, and forget it."""
    pool = nu.mp_pool.PoolRef()
    return nu.IfDo(
        Runner.worker.not_empty(),
        nu.Let(
            f"{ns}.old",
            Runner.worker,
            body=pool.kill(nu.IntAttrRef(f"{ns}.old")) >> Runner.worker.erase(),
        ),
    )


def page_tree(
    page_id: nu.StrArg,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    body: nu.Nu | None = None,
    alongside: nu.Nu | None = None,
    duration: float | None = None,
) -> nu.Nu:
    """One page, running and restarting on every section write, as one term.

    No ``With`` head: the store, the pool and the ``dict`` behind
    ``Runner.worker`` all come from the context this is run in, so a preset
    can give each view its own without this module knowing about views.

    Args:
        page_id: the page to run.
        session_address: where this connection's Session is served. See
            :func:`page_body`.
        root: the space's root Shape class.
        body: the term dispatched for the page. See :func:`run_page`.
        alongside: a tree to run beside the live loop, for demos and tests.
        duration: stop after this many seconds. None runs forever.

    Returns:
        The tree, already bracketed for atomicity against ``root``.
    """
    root = resolve_root(root)
    sections = root.pages[page_id].sections

    def start() -> nu.Nu:
        # Built per use: one node in two tree positions is one node.
        return run_page(
            nu.str(page_id), session_address=session_address, root=root, body=body, ns="tree"
        )

    # The container must exist before anything reads it: a subscription over a
    # missing container resolves to INVALID and silently never fires.
    # Dict.create(), not {} -- a literal dict is captured once at Form
    # construction and shared across every evaluation of the term.
    boot = sections.init(nu.Dict.create())
    # The bare key naming no section also fires. It must be skipped
    # explicitly: indexing past the end raises IndexError inside the react
    # loop, killing it and leaving the runner silently deaf.
    live = nu.ReactForever(
        sections.on_change(),
        nu.IfDo(nu.Len(_KEY) > nu.Int(CHANGED_SECTION_INDEX), start()),
        changed_key="k",
    )
    flow = live if alongside is None else (live | alongside)
    if duration is not None:
        flow = nu.Race(flow, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    return nu.kv.auto_flow_atomic(boot >> start() >> flow, scope=root)
