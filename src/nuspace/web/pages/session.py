"""The page supervisor for one connection: whatever this tab is on, running.

An app is space-wide, so one supervisor per process runs every app forever; a
section belongs to a page and a page belongs to a view, so this is mounted per
connection and follows that tab's route.

Two stable arms and a ``nu.mem`` cell. The select arm hears the browser
navigate and writes the new page id into the cell; the store arm hears the
space's sections change and reconciles the one that changed, if it is on the
page the cell names. The cell is read at event time and never subscribed to,
which is why neither arm is ever rebuilt and nothing polls anything.

Both arms call the same ``reconcile``, under their own attr names so neither
can read the other's binding. Reconcile is stop-then-start on one section, so
a section written to several times over restarts several times -- correct, and
noisier than it needs to be. Coalescing is a v1.1 problem.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mem
import nu.mp_pool
from nuspace._root import resolve_root
from nuspace.pages import ops
from nuspace.pages.runner import CHANGED_SECTION_INDEX, reconcile
from nuspace.pages.shapes import WORKERS_SLOT, Runner
from nuspace.web.arms import Arms, field_str


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang.runtime import Context
    from nuspace.web.pages.ref import PagesRef


__all__ = [
    "CHANGED_PAGE_INDEX",
    "SECTIONS_INDEX",
    "SECTIONS_SEGMENT",
    "SectionWorkers",
    "Tab",
    "cell",
    "page_session",
]


#: Position of the page id in a key from ``Space.pages.on_change()``. The
#: subscription is space-wide and depth-unbounded, so a section key reads
#: ``('/', 'pages', page_id, 'sections', section_id)`` with an optional field
#: after it. Pinned by ``tests/nuspace/pages/test_changed_key.py``.
CHANGED_PAGE_INDEX = 2

#: Where ``Page.sections`` sits in that key, and what it spells. A page's other
#: slots live at the same depth, so this is what tells a section key apart.
SECTIONS_INDEX = 3
SECTIONS_SEGMENT = "sections"


class Tab(nu.Shape):
    """What one connection knows: the page it is looking at.

    ``nu.mem``, written by the select arm and read by the store arm. It is
    never subscribed to -- a mem ref has no ``on_change``, and none is wanted.
    """

    page = nu.mem.StrRef.slot()


def cell() -> nu.Nu:
    """The page this tab is on, as a string, always.

    A slot nothing has written yet reads EMPTY, and EMPTY in a comparison is
    INVALID rather than False -- which would swallow the first select of every
    connection. Built per use: one node in two tree positions is one node.
    """
    return nu.If(nu.NotEmpty(Tab.page), Tab.page, nu.Str(""))


class SectionWorkers(dict):
    """This connection's ``Runner.workers`` dict, and the workers in it.

    Bound as the ``dict`` behind the pages ``Runner``, so the records the arms
    write land here and bracket close kills whatever is still on record.
    """

    __slots__ = ("_pool",)

    def setup(self, ctx: Context) -> None:
        """Hold the process-wide pool the records name workers in."""
        self._pool = ctx.get(nu.mp_pool.WorkerPool)

    def cleanup(self) -> None:
        """Kill every worker this connection still has on record.

        Inline and sync, like the pool's own teardown, so a cancellation
        landing on the connection cannot abandon a half-reaped tab.
        """
        for worker in list(self.get(WORKERS_SLOT, {}).values()):
            self._pool.kill(worker)


#: Every arm here, labelled for the reports it prints.
_arms = Arms("session")

#: The two arms' attrs namespaces. Parallel arms share one ``ctx.attrs``.
_SELECT = "select"
_STORE = "store"

#: What each pass binds the section it is about under. Two arms, two names.
_SEED_ITEM = "session.seed"
_LIVE_ITEM = "session.live"

#: And where each parks the page it is working on. An attr, not the cell: a
#: dispatched body is evaluated in the worker, and ``carry=True`` ships attrs
#: there while the cell -- like every mem slot -- stays in this process.
_SEED_PAGE = "session.seed.page"
_LIVE_PAGE = "session.live.page"

#: The page the browser just navigated to, straight off the select event.
_selected = field_str(_SELECT, "page_id")

#: The kv key that woke the store arm, and the two ids inside it.
_KEY = nu.TupleAttrRef(_STORE)
_changed_page = _KEY[CHANGED_PAGE_INDEX]
_changed_section = _KEY[CHANGED_SECTION_INDEX]


def _addressable(page_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """Whether ``page_id`` names a page that is really there.

    The emptiness test is not redundant: a kv key may not hold an empty
    segment, so ``pages[""]`` raises out of the codec rather than reading as
    absent, and ``And`` short-circuiting is what keeps the guard total.
    """
    return nu.And(nu.Ne(page_id, nu.Str("")), ops.page_exists(page_id, root=root))


def _stop_recorded() -> nu.Nu:
    """Kill every worker this connection has on record.

    The records only ever name the page being left, so this is that page's
    sections and no others.
    """
    item = nu.StrAttrRef(_SEED_ITEM)
    pool = nu.mp_pool.PoolRef()
    stop = pool.kill(Runner.workers[item]) >> Runner.workers.del_item(item)
    # Guarded because a tab that has not arrived anywhere yet reads EMPTY
    # rather than an empty dict.
    return nu.IfDo(
        nu.NotEmpty(Runner.workers),
        nu.ForEachDo(nu.list(Runner.workers.keys()), stop, item=_SEED_ITEM),
    )


def _seed(root: type[Shape]) -> nu.Nu:
    """Start every section on the page bound at ``_SEED_PAGE``.

    ``Launch`` and ``Dispatch`` both return as soon as the worker has the
    body, so this walk does not block the arm it runs in.
    """
    page = nu.StrAttrRef(_SEED_PAGE)
    sections = root.pages[page].sections
    boot = sections.init(nu.Dict.create()) >> Runner.workers.init(nu.Dict.create())
    pass_ = reconcile(page, root=root, item=_SEED_ITEM)
    return nu.IfDo(
        _addressable(page, root),
        # nu.list is load-bearing: the keys view is lazy and auto_flow_atomic
        # brackets the items slot separately, so an undrained view outlives
        # its Snapshot and dies with StorageClosedError.
        boot >> nu.ForEachDo(nu.list(sections.keys()), pass_, item=_SEED_ITEM),
    )


def _on_select(root: type[Shape]) -> nu.Nu:
    """Leave the page the cell names, move the cell, start the new page.

    The event carries the page id, so nothing here reads the route back off
    the browser. A select naming the page already in the cell is skipped,
    which is what makes the browser's repeat sends free.
    """
    return nu.IfDo(
        nu.Ne(_selected, cell()),
        _stop_recorded()
        >> Tab.page.set(_selected)
        >> nu.Let(_SEED_PAGE, _selected, body=_seed(root)),
    )


def _on_store(root: type[Shape]) -> nu.Nu:
    """Reconcile the section that changed, if this tab is on its page.

    The key carries both ids, so page membership is read off the event rather
    than looked up, and the cell is read here rather than subscribed to --
    which is what lets this one subscription outlive every navigation.
    """
    mine = nu.And(
        # The bare page key and every non-section slot fire too, and indexing
        # past the end would raise inside the react loop and leave the arm
        # silently deaf.
        nu.Len(_KEY) > nu.Int(CHANGED_SECTION_INDEX),
        nu.Eq(_KEY[SECTIONS_INDEX], nu.Str(SECTIONS_SEGMENT)),
        nu.Eq(_changed_page, cell()),
    )
    pass_ = reconcile(nu.StrAttrRef(_LIVE_PAGE), root=root, item=_LIVE_ITEM)
    return nu.IfDo(
        mine,
        nu.Let(_LIVE_PAGE, cell(), body=nu.Let(_LIVE_ITEM, _changed_section, body=pass_)),
    )


def page_session(pages: PagesRef, *, root: type[Shape] | None = None) -> nu.Nu:
    """This connection's page, supervised, for as long as the connection lasts.

    Args:
        pages: the ``PagesRef`` on the mounted shell. The select arm's
            subscription, and the only place the route enters this tree.
        root: the space's root Shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never finishes,
        which is the contract the ws endpoint holds every per-connection tree
        to.
    """
    root = resolve_root(root)
    flow = _arms.event(_SELECT, pages.on_select(), _on_select(root)) | _arms.event(
        _STORE, root.pages.on_change(), _on_store(root)
    )
    return nu.With(
        # Tagged, both of them. A pages ``Runner.workers`` and an apps
        # ``Runner.workers`` are the same key by name in the process-wide
        # dict, and two tabs on one page would write each other's records.
        nu.Provide(dict, {}, tags=(Tab,)),
        nu.Provide(SectionWorkers, {}, tags=(Runner,), bind_as=dict),
        # One bracket over the whole fold, like every other driver: the store
        # arm's own subscription reads a container, so it needs a snapshot as
        # much as the body it wakes does.
        body=nu.kv.auto_flow_atomic(flow, scope=root),
    )
