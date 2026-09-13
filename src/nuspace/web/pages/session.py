"""The page supervisor for one connection: whatever this tab is on, running.

An app is space-wide, so one supervisor per process runs every app forever; a
page belongs to a view, so this is mounted per connection and follows that
tab's route.

Two stable arms and a ``nu.mem`` cell. The select arm hears the browser
navigate and writes the new page id into the cell; the store arm hears the
space's sections change and restarts the page, if the write landed on the page
the cell names. The cell is read at event time and never subscribed to, which
is why neither arm is ever rebuilt and nothing polls anything.

Both arms converge on one operation -- ``run_page`` -- under their own attr
names so neither can read the other's binding. It is one worker for the whole
page, so editing one section restarts its siblings too. Accepted for v1: a
worker is all or nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
import nu.mem
import nu.mp_pool
from nuspace._root import resolve_root
from nuspace.pages import ops
from nuspace.pages.runner import CHANGED_SECTION_INDEX, run_page
from nuspace.pages.shapes import WORKER_SLOT, Runner
from nuspace.web.arms import Arms, field_str


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang.runtime import Context
    from nuspace.web.pages.ref import PagesRef


__all__ = [
    "CHANGED_PAGE_INDEX",
    "SECTIONS_INDEX",
    "SECTIONS_SEGMENT",
    "PageWorker",
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


class PageWorker(dict):
    """This connection's ``Runner.worker`` record, and the worker in it.

    Bound as the ``dict`` behind the pages ``Runner``, so the record the arms
    write lands here and bracket close kills whatever is still on it.
    """

    __slots__ = ("_pool",)

    def setup(self, ctx: Context) -> None:
        """Hold the process-wide pool the record names a worker in."""
        self._pool = ctx.get(nu.mp_pool.WorkerPool)

    def cleanup(self) -> None:
        """Kill the worker this connection still has on record.

        Inline and sync, like the pool's own teardown, so a cancellation
        landing on the connection cannot abandon a half-reaped tab.
        """
        worker = self.get(WORKER_SLOT)
        if isinstance(worker, int):
            self._pool.kill(worker)


#: Every arm here, labelled for the reports it prints.
_arms = Arms("session")

#: The two arms' attrs namespaces. Parallel arms share one ``ctx.attrs``, and
#: ``run_page`` binds three attrs of its own under whichever it is given.
_SELECT = "select"
_STORE = "store"

#: The page the browser just navigated to, straight off the select event.
_selected = field_str(_SELECT, "page_id")

#: The kv key that woke the store arm, and the page id inside it.
_KEY = nu.TupleAttrRef(_STORE)
_changed_page = _KEY[CHANGED_PAGE_INDEX]


def _addressable(page_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """Whether ``page_id`` names a page that is really there.

    The emptiness test is not redundant: a kv key may not hold an empty
    segment, so ``pages[""]`` raises out of the codec rather than reading as
    absent, and ``And`` short-circuiting is what keeps the guard total.
    """
    return nu.And(nu.Ne(page_id, nu.Str("")), ops.page_exists(page_id, root=root))


def _run(page: nu.Nu, root: type[Shape], session_address: str, ns: str) -> nu.Nu:
    """Make this connection run ``page``, if that page is really there.

    ``Launch`` and ``Dispatch`` both return as soon as the worker has the
    body, so this does not block the arm it runs in.
    """
    return nu.IfDo(
        _addressable(page, root),
        run_page(page, session_address=session_address, root=root, ns=ns),
    )


def _on_select(root: type[Shape], session_address: str) -> nu.Nu:
    """Move the cell, then run the page it now names.

    The event carries the page id, so nothing here reads the route back off
    the browser. A select naming the page already in the cell is skipped,
    which is what makes the browser's repeat sends free.
    """
    return nu.IfDo(
        nu.Ne(_selected, cell()),
        Tab.page.set(_selected) >> _run(_selected, root, session_address, _SELECT),
    )


def _on_store(root: type[Shape], session_address: str) -> nu.Nu:
    """Restart this tab's page, if the write landed on it.

    Which section changed does not matter: the page is the unit, so any
    section write is a page restart. The key carries the page id, so
    membership is read off the event rather than looked up, and the cell is
    read here rather than subscribed to -- which is what lets this one
    subscription outlive every navigation.
    """
    mine = nu.And(
        # The bare page key and every non-section slot fire too, and indexing
        # past the end would raise inside the react loop and leave the arm
        # silently deaf.
        nu.Len(_KEY) > nu.Int(CHANGED_SECTION_INDEX),
        nu.Eq(_KEY[SECTIONS_INDEX], nu.Str(SECTIONS_SEGMENT)),
        nu.Eq(_changed_page, cell()),
    )
    return nu.IfDo(mine, _run(cell(), root, session_address, _STORE))


def page_session(
    pages: PagesRef, *, session_address: str, root: type[Shape] | None = None
) -> nu.Nu:
    """This connection's page, supervised, for as long as the connection lasts.

    Args:
        pages: the ``PagesRef`` on the mounted shell. The select arm's
            subscription, and the only place the route enters this tree.
        session_address: where this connection's ``nu.ui`` Session is served.
            Per connection, not per process, which is why it arrives here and
            not in the pool's ``worker_init``.
        root: the space's root Shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never finishes,
        which is the contract the ws endpoint holds every per-connection tree
        to.
    """
    root = resolve_root(root)
    flow = _arms.event(_SELECT, pages.on_select(), _on_select(root, session_address)) | _arms.event(
        _STORE, root.pages.on_change(), _on_store(root, session_address)
    )
    return nu.With(
        # Tagged, both of them. A pages ``Runner`` and an apps ``Runner`` are
        # the same key by name in the process-wide dict, and two tabs on one
        # page would write each other's records.
        nu.Provide(dict, {}, tags=(Tab,)),
        nu.Provide(PageWorker, {}, tags=(Runner,), bind_as=dict),
        # One bracket over the whole fold, like every other driver: the store
        # arm's own subscription reads a container, so it needs a snapshot as
        # much as the body it wakes does.
        body=nu.kv.auto_flow_atomic(flow, scope=root),
    )
