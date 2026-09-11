"""LensDriver -- one connection's Lens program.

The Control is thin on purpose. It makes the one per-connection object
(the View), resolves the ref's wire path so the op addresses can be built
from it, composes a term and runs it.

    FirstPaint >> (
        ops.dispatch      one ReactForever per op path
      | ship.columns      ForeverDo(Write(ref, Payload(next_columns)))
    )

Boot is sequential before the parallel body so the root column is queued
before the loop starts. It would work either way -- the queue holds -- but
the order says what is meant: paint first, then listen.

There is no teardown. ``ReactForever`` closes its own subscription in a
``finally``, and a lens owns no processes, no fabrics and no handles. The
queue is garbage when the connection is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Control
from nuspace.web.refs.common import AsyncOnly, Perform
from nuspace.web.refs.lens import ops, ship
from nuspace.web.refs.lens.view import View


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime
    from nuspace.web.refs.lens.ref import LensRef


__all__ = ["LensDriver"]


class LensDriver(AsyncOnly, Control):
    """Per-connection driver for the Lens surface."""

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: LensRef) -> None:
        super().__init__(ref)

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: LensRef = self._children[0]
        root = ref.root
        max_rows = ref.max_rows

        async def athunk(rt: Runtime) -> None:
            ref_nid = rt.program.children[nid][0]
            base = await ref._aresolve_address(rt, ref_nid)
            view = View(rt.ctx, root, max_rows)

            async def first_paint() -> None:
                """Ask for the root column before anyone has navigated.

                Reload starts here every time. Persisting the cursor is an
                explicit v2 choice -- backing it with a fabric -- not an
                accident of server-held state.
                """
                view.request(())

            boot = Perform(ref, first_paint, label="first_paint")
            body = ops.dispatch(base, ref, view) | ship.columns(ref, view)

            await nu.arun(boot >> body, rt.ctx)  # type: ignore[arg-type]

        return athunk
