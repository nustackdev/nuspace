"""AppsDriver -- one connection's Apps program.

The Control is thin on purpose. All it does is the one thing that cannot
be said in Nu: make the per-connection objects, and resolve the ref's
wire path, which the op addresses are built from. Then it composes a term
out of them and runs it.

    InitApps >> FirstPaint >> (
        ops.dispatch      one ReactForever per op path
      | ship.watch        one kv subscription, the whole apps subtree
      | ship.apps         ForeverDo(Write(ref, Payload(next_apps)))
      | ship.status       ForeverDo(Write(ref, Payload(next_status)))
    )

Boot is sequential before the parallel body for two reasons. The apps
container has to exist before ``on_change`` is asked for a subscription,
or the address resolves through a missing container and answers INVALID.
And the payload has to be marked stale before the loops start, or the
first paint waits for a write that may never come.

## What this driver does not do

It does not run anything, and that is the whole structural difference
from ``PagesDriver``, which owns its supervisor. An app runs whether or
not a browser is looking, so its supervisor lives at space lifetime in
the app tree (``runner.py``). This driver observes it, through
``View.observe``. Two browsers therefore see one set of running apps
rather than one set each, and a browser that connects mid-run paints what
is already running instead of starting it.

Teardown is the ``finally`` inside ``arun``: every ``ReactForever``
closes its own subscription, and ``view.dispose`` drops this connection's
status listener off a runtime that outlives it. Nothing else unbinds by
hand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Control
from nuspace.web.refs.apps import ops
from nuspace.web.refs.apps.interactions import AppOps, ship
from nuspace.web.refs.apps.view import View
from nuspace.web.refs.common import AsyncOnly, Perform


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime
    from nuspace.web.refs.apps.ref import AppsRef


__all__ = ["AppsDriver"]


class AppsDriver(AsyncOnly, Control):
    """Per-connection driver for the Apps surface."""

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: AppsRef) -> None:
        super().__init__(ref)

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: AppsRef = self._children[0]
        root = ref.space_root

        async def athunk(rt: Runtime) -> None:
            ref_nid = rt.program.children[nid][0]
            base = await ref._aresolve_address(rt, ref_nid)

            view = View(rt.ctx, root)
            app = AppOps(view)

            async def first_paint() -> None:
                """Ask for the list before anything has changed."""
                view.apps_dirty.mark()

            boot = Perform(root.apps, app.init_apps, label="init_apps") >> Perform(
                ref,
                first_paint,
                label="first_paint",
            )

            body = (
                ops.dispatch(base, ref, view)
                | ship.watch(ref, root, view)
                | ship.apps(ref, view)
                | ship.status(ref, view)
            )

            try:
                await nu.arun(boot >> body, rt.ctx)  # type: ignore[arg-type]
            finally:
                await view.dispose()

        return athunk
