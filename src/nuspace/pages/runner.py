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

**The worker manages its own sections.** It hears the store through the
proxied observer ``worker_init`` binds, so a page changing is a reload inside
the process it is already running in, never a new one. Two nested levels, and
the two subscriptions are deliberately different:

- the fold sits under ``sections.on_children_change()``, which is length
  exact: it fires when a section is added or removed, never when one is
  edited, and that is when the set of arms changed and the fold has to be
  rebuilt.
- each arm sits under ``sections[sid].on_change()``, which is depth
  unbounded: any write inside that one section restarts that one arm and
  leaves its siblings running.

``Race`` is what does the restarting. The body and a ``React`` on the
subscription run side by side, the change cancels the body, and the
``ForeverDo`` re-enters and reloads from the store. Killing a worker is left
for the things that really need a fresh process: navigating, and the
connection going away.

**Navigation dispatches into a spare.** The kill stays, and so does the fresh
process, but the process is one this connection launched a navigation ago and
has been holding idle. ``Runner`` keeps two slots for that reason, and the
launch that refills the idle one runs beside the dispatch rather than in front
of it. It is policy, so it is here: the pool serves apps too, and an app never
wants a spare.
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
    "SECTION_ATTR",
    "page_body",
    "page_tree",
    "run_page",
    "section_arm",
    "stop_page",
]


#: What the fold binds each section id under, inside the worker. Every arm
#: gets its own Context branch, so one name serves every section and no caller
#: has to namespace it.
SECTION_ATTR = "section"

#: Where an arm parks the term it just constructed. Arm-local for the same
#: reason ``SECTION_ATTR`` is.
_TERM_ATTR = "section.term"

#: Whether the section this arm is for is still in the store. Read once per
#: turn of the arm's loop, because a delete wakes the arm before it removes it.
_ALIVE_ATTR = "section.alive"

#: How long a parked branch sleeps before waking to do nothing. Finite only
#: because ``Delay`` takes a number; a branch that parks is waiting to be
#: cancelled, never to time out.
_PARK_SECONDS = 3600.0


def _park() -> nu.Nu:
    """Sit on the loop doing nothing, until something cancels this branch.

    What a branch that has nothing left to do does instead of returning. A
    ``Race`` ends when its first child finishes, so a body that returns would
    restart the loop around it immediately and spin.
    """
    return nu.ForeverDo(nu.Delay(nu.Float(_PARK_SECONDS)))


def _restarts_on(change: nu.Nu, body: nu.Nu, *, root: type[Shape]) -> nu.Nu:
    """``body``, run again from the store every time ``change`` fires.

    The two race: the change cancels the body, the loop re-enters, and the
    subscription is opened fresh on the way in. ``body`` is parked behind
    rather than returned from, so a body that ends early waits for the change
    like a body that never ends.

    Args:
        change: the subscription to restart on. Built per call -- one node in
            two tree positions is one node.
        body: what runs until the change comes.
        root: the space's root Shape class, for the subscription's bracket.
    """
    return nu.ForeverDo(
        nu.Race(
            body >> _park(),
            # The subscription resolves a container, so it needs a snapshot as
            # much as anything reading one does.
            nu.kv.auto_flow_atomic(nu.React(change, nu.Noop()), scope=root),
        )
    )


def section_arm(
    page_id: nu.StrArg, *, root: type[Shape] | None = None, item: str = SECTION_ATTR
) -> nu.Nu:
    """One section, constructed and running and reloading, as one arm of the fold.

    The section arrives as the attr ``item``, bound by the fold. It restarts
    itself on any write inside its own subtree and nothing else, so editing one
    block leaves every other block on the page running. Three ``TryCatch``
    layers, and none is optional: the fold cancels every sibling arm on the
    first error, so a section that dies has to die alone.

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
    # as `failed`, and both end this turn quietly rather than raising into the
    # fold. Nothing retries here: the section stays failed until its own
    # subscription says it changed.
    guarded = nu.TryCatch(run, catch=report, errors=nu.prog.ConstructionError)
    once = clear >> nu.TryCatch(guarded, catch=report)
    # A delete wakes this arm before the fold above it is rebuilt, so the turn
    # after one lands is a turn with no section to load. Read once, per turn,
    # rather than trusted from fan-out time.
    turn = nu.Let(
        _ALIVE_ATTR,
        nu.kv.auto_flow_atomic(sections.contains(section), scope=root),
        body=nu.IfDo(nu.BoolAttrRef(_ALIVE_ATTR), once),
    )
    # Third layer, and the one the other two cannot cover: opening the
    # subscription is outside the body they guard, and a section deleted at
    # exactly the wrong moment resolves to no view at all. Park instead of
    # raising -- the fold is about to be rebuilt without this arm anyway.
    return nu.TryCatch(_restarts_on(sections[section].on_change(), turn, root=root), catch=_park())


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
    are: this is the process with the store. And it is re-read whenever the set
    of sections changes, which is what makes adding a block cost no process.

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
    # arm is a section that runs until it is cancelled. The items are read once
    # at fan-out, so a section added later is picked up by the rebuild below
    # and never by reaching into a live fold.
    fold = nu.ForEachParAsync(ids, section_arm(page_id, root=root, item=item), item=item)
    live = _restarts_on(sections.on_children_change(), fold, root=root)
    # The observer sits here rather than in ``worker_init``: a snippet with a
    # kv subscription needs one bound, and a pool whose every worker pays for
    # it on the way up makes a restart slow enough to see. Once per page now,
    # not once per section. It is also what the two loops above subscribe
    # through, so nothing here works without it.
    guarded = nu.With(spare_observer(), body=live)
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


def _take_spare() -> nu.Nu:
    """The spare's id if this connection has one, a fresh cold launch if not.

    ``If`` short-circuits, which is the whole trick: the launch sits in the
    branch that only runs when the slot is empty, so a warm navigation never
    reaches the pool's spawn path at all. This only reads the slot; the caller
    is what empties it.
    """
    return nu.If(Runner.spare.not_empty(), Runner.spare, nu.mp_pool.PoolRef().launch())


def run_page(
    page: nu.Nu,
    *,
    session_address: str | None = None,
    root: type[Shape] | None = None,
    body: nu.Nu | None = None,
    ns: str = "page",
) -> nu.Nu:
    """Make this connection run ``page``, whatever it was running before.

    The hard kill, and the only one left: arriving on a page, and nothing else.
    A section changing is the worker's own business now. What is left to pay
    for is the spawn, so this does not spawn: it dispatches into the spare this
    connection has been holding, and the launch that refills the slot happens
    beside the dispatch rather than in front of it.

    Three things run at once once the target is picked, and the order they
    finish in does not matter: the body goes to the warm worker, the worker
    that was on record dies, and a new spare comes up for next time. Only the
    first is on the path to the page appearing.

    Cold and exhausted both fall back to the old behaviour rather than to an
    error. A connection's first navigation has no spare, and clicking faster
    than a launch takes will run the slot empty; both land on a plain launch,
    which is exactly what every navigation used to cost.

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
    # The worker subscribes to this container, and a subscription over a
    # missing one resolves to nothing rather than waiting, so a page that never
    # had a section would never hear its first. Written here rather than in the
    # body because ``Dict.create()`` does not survive the pickle to the child,
    # and a literal dict would be captured once at Form construction and shared
    # across every evaluation of the term.
    boot = root.pages[nu.StrAttrRef(page_attr)].sections.init(nu.Dict.create())
    # Emptied before the refill rather than overwritten by it: a launch that
    # raises would otherwise leave the slot naming the worker now running the
    # page, and the next navigation would dispatch a second body into it.
    claim = nu.IfDo(Runner.spare.not_empty(), Runner.spare.erase())
    return nu.Let(
        page_attr,
        page,
        # A slot nothing has written yet reads EMPTY, and EMPTY through a kill
        # is a lookup for a worker that never existed.
        body=boot
        >> nu.Let(
            old_attr,
            nu.If(Runner.worker.not_empty(), Runner.worker, nu.Int(-1)),
            body=nu.Let(
                new_attr,
                _take_spare(),
                body=claim
                >> nu.Parallel(
                    dispatch >> Runner.worker.set(started),
                    nu.IfDo(stopped >= nu.Int(0), pool.kill(stopped)),
                    # The one that must not be sequenced in front of the
                    # dispatch. Moving the spawn is not hiding it.
                    Runner.spare.set(pool.launch()),
                ),
            ),
        ),
    )


def stop_page(*, ns: str = "page") -> nu.Nu:
    """Kill both workers on record, if there are any, and forget them.

    The spare counts. It is holding no body and nobody is looking at it, and it
    is still a live process, so a teardown that reaps only the running one
    leaks one process per connection.
    """
    pool = nu.mp_pool.PoolRef()
    return nu.IfDo(
        Runner.worker.not_empty(),
        nu.Let(
            f"{ns}.old",
            Runner.worker,
            body=pool.kill(nu.IntAttrRef(f"{ns}.old")) >> Runner.worker.erase(),
        ),
    ) >> nu.IfDo(
        Runner.spare.not_empty(),
        nu.Let(
            f"{ns}.idle",
            Runner.spare,
            body=pool.kill(nu.IntAttrRef(f"{ns}.idle")) >> Runner.spare.erase(),
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
    """One page, launched once and left to run itself, as one term.

    No ``With`` head: the store, the pool and the ``dict`` behind
    ``Runner.worker`` all come from the context this is run in, so a preset
    can give each view its own without this module knowing about views.

    One launch is the whole of it. The worker follows its own sections, so
    there is nothing here to restart and nothing here to subscribe to; this
    just holds the page open for as long as it is asked to.

    Args:
        page_id: the page to run.
        session_address: where this connection's Session is served. See
            :func:`page_body`.
        root: the space's root Shape class.
        body: the term dispatched for the page. See :func:`run_page`.
        alongside: a tree to run beside the running page, for demos and tests.
        duration: stop after this many seconds. None runs forever.

    Returns:
        The tree, already bracketed for atomicity against ``root``.
    """
    root = resolve_root(root)
    start = run_page(
        nu.str(page_id), session_address=session_address, root=root, body=body, ns="tree"
    )
    # Launch and Dispatch both return as soon as the worker has the body, so
    # something has to hold the tree open or the bracket would reap the worker
    # it just started.
    flow = _park() if alongside is None else (_park() | alongside)
    if duration is not None:
        flow = nu.Race(flow, nu.DelayedDo(nu.Float(duration), nu.Noop()))
    return nu.kv.auto_flow_atomic(start >> flow, scope=root)
