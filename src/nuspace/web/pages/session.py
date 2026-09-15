"""The page supervisor for one connection: whatever this tab is on, running.

An app is space-wide, so one supervisor per process runs every app forever; a
page belongs to a view, so this is mounted per connection and follows that
tab's route.

One arm and a ``nustd.mem`` cell. The arm hears the browser navigate, writes the
new page id into the cell, and runs that page. The cell is read at event time
and never subscribed to, which is why the arm is never rebuilt and nothing
polls anything.

Navigation is the only thing here that kills a worker, and that is the whole
supervisor. A section being added, edited or deleted never reaches this
module: the worker hears the store itself and reloads in place, so what used
to be a process spawn per keystroke is now a term re-entering a loop. See
:mod:`nuspace.pages.runner`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
import nustd.mem
import nustd.mp_pool
from nuspace._root import resolve_root
from nuspace.pages import ops
from nuspace.pages.runner import run_page
from nuspace.pages.shapes import SPARE_SLOT, WORKER_SLOT, Runner
from nuspace.web.arms import Arms, field_str


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang.runtime import Context
    from nuspace.web.pages.ref import PagesRef


__all__ = ["PageWorker", "Tab", "cell", "page_session"]


class Tab(nu.Shape):
    """What one connection knows: the page it is looking at.

    ``nustd.mem``, written and read by the select arm. It is never subscribed to
    -- a mem ref has no ``on_change``, and none is wanted.
    """

    page = nustd.mem.StrRef.slot()


def cell() -> nu.Nu:
    """The page this tab is on, as a string, always.

    A slot nothing has written yet reads EMPTY, and EMPTY in a comparison is
    INVALID rather than False -- which would swallow the first select of every
    connection. Built per use: one node in two tree positions is one node.
    """
    return nu.If(nu.NotEmpty(Tab.page), Tab.page, nu.Str(""))


class PageWorker(dict):
    """This connection's ``Runner`` record, and the workers in it.

    Bound as the ``dict`` behind the pages ``Runner``, so the records the arm
    writes land here and bracket close kills whatever is still on them.
    """

    __slots__ = ("_pool",)

    def setup(self, ctx: Context) -> None:
        """Hold the process-wide pool the records name workers in."""
        self._pool = ctx.get(nustd.mp_pool.WorkerPool)

    def cleanup(self) -> None:
        """Kill both workers this connection still has on record.

        Both, because the spare is a live process that happens to be idle: a
        teardown reaping only the running one leaks a whole interpreter every
        time a tab closes. Either slot may be empty -- a connection that never
        navigated has no worker, and one that navigated faster than a launch
        has no spare.

        Inline and sync, like the pool's own teardown, so a cancellation
        landing on the connection cannot abandon a half-reaped tab.
        """
        for slot in (WORKER_SLOT, SPARE_SLOT):
            worker = self.get(slot)
            if isinstance(worker, int):
                self._pool.kill(worker)


#: The arm here, labelled for the reports it prints.
_arms = Arms("session")

#: The arm's attrs namespace. ``run_page`` binds three attrs of its own under
#: whatever it is given.
_SELECT = "select"

#: The page the browser just navigated to, straight off the select event.
_selected = field_str(_SELECT, "page_id")


def _addressable(page_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """Whether ``page_id`` names a page that is really there.

    The emptiness test is not redundant: a kv key may not hold an empty
    segment, so ``pages[""]`` raises out of the codec rather than reading as
    absent, and ``And`` short-circuiting is what keeps the guard total.
    """
    return nu.And(nu.Ne(page_id, nu.Str("")), ops.page_exists(page_id, root=root))


def _run(page: nu.Nu, pages: PagesRef, root: type[Shape], session_address: str, ns: str) -> nu.Nu:
    """Make this connection run ``page``, if that page is really there.

    ``Launch`` and ``Dispatch`` both return as soon as the worker has the
    body, so this does not block the arm it runs in.
    """
    return nu.IfDo(
        _addressable(page, root),
        run_page(page, surface=pages, session_address=session_address, root=root, ns=ns),
    )


def _on_select(pages: PagesRef, root: type[Shape], session_address: str) -> nu.Nu:
    """Move the cell, then run the page it now names.

    The event carries the page id, so nothing here reads the route back off
    the browser. A select naming the page already in the cell is skipped,
    which is what makes the browser's repeat sends free.
    """
    return nu.IfDo(
        nu.Ne(_selected, cell()),
        Tab.page.set(_selected) >> _run(_selected, pages, root, session_address, _SELECT),
    )


def page_session(
    pages: PagesRef, *, session_address: str, root: type[Shape] | None = None
) -> nu.Nu:
    """This connection's page, supervised, for as long as the connection lasts.

    Args:
        pages: the ``PagesRef`` on the shell. Two jobs: the arm's subscription,
            which is the only place the route enters this tree, and the node
            every section on the page roots its ui refs under.
        session_address: where this connection's ``nustd.ui`` Session is served.
            Per connection, not per process, which is why it arrives here and
            not in the pool's ``worker_init``.
        root: the space's root Shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never finishes,
        which is the contract the ws endpoint holds every per-connection tree
        to.
    """
    root = resolve_root(root)
    flow = _arms.event(_SELECT, pages.on_select(), _on_select(pages, root, session_address))
    return nu.With(
        # Tagged, both of them. A pages ``Runner`` and an apps ``Runner`` are
        # the same key by name in the process-wide dict, and two tabs on one
        # page would write each other's records.
        nu.Provide(dict, {}, tags=(Tab,)),
        nu.Provide(PageWorker, {}, tags=(Runner,), bind_as=dict),
        # One bracket over the arm, like every other driver: its own
        # subscription reads a container, so it needs a snapshot as much as
        # the body it wakes does.
        body=nustd.kv.auto_flow_atomic(flow, scope=root),
    )
