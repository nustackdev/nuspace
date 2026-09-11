"""PagesDriver -- one connection's Pages program.

The Control is thin on purpose. All it does is the one thing that cannot
be said in Nu: make the per-connection objects (this connection's
supervisor and cursor), and resolve the ref's wire path, which the op
addresses are built from. Then it composes a term out of them and runs
it.

    InitRoot >> FirstPaint >> (
        ops.dispatch      one ReactForever per op path
      | ship.watch        one kv subscription, whole page subtree
      | ship.tree         ForeverDo(Write(ref, Payload(next_tree)))
      | ship.page         ForeverDo(Write(...) >> Launch)
      | ship.status       ForeverDo(Write(ref, Payload(next_status)))
    )

Boot is sequential before the parallel body for two reasons. The root
page has to exist before ``on_change`` is asked for a subscription, or
the address resolves through a missing container and answers INVALID.
And both payloads have to be marked stale before the loops start, or the
first paint waits for a write that may never come.

The cursor's fabric is bound on Context here rather than by a
``nu.Provide`` in the tree, for the same reason the ws host binds
``Session`` in python: the program below needs to read it, and a bracket
inside the tree would put the binding out of the Control's reach. The
cursor itself is still a Ref -- ``Cursor.path`` in ``view.py`` -- which
is the part that matters.

The teardown is the ``finally`` inside ``arun``: every ``ReactForever``
closes its own subscription, and the Control stops the sections it was
running. Nothing here unbinds by hand.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Control
from nuspace.web.refs.common import AsyncOnly, Perform
from nuspace.web.refs.pages import ops
from nuspace.web.refs.pages.interactions import PageOps, ship
from nuspace.web.refs.pages.view import Cursor, View


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime
    from nuspace.web.refs.pages.ref import PagesRef


__all__ = ["PagesDriver"]


class PagesDriver(AsyncOnly, Control):
    """Per-connection driver for the Pages surface."""

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: PagesRef) -> None:
        super().__init__(ref)

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: PagesRef = self._children[0]
        root = ref.space_root

        async def athunk(rt: Runtime) -> None:
            ref_nid = rt.program.children[nid][0]
            base = await ref._aresolve_address(rt, ref_nid)

            # This connection's own scratch memory for `Cursor`, alongside
            # the Session the ws host already bound.
            ctx = rt.ctx.bind(dict, {}, Cursor)
            view = View(ctx, root)
            pages = PageOps(view)

            async def first_paint() -> None:
                """Ask for both payloads before anything has changed."""
                view.tree_dirty.mark()
                view.page_dirty.mark()

            boot = Perform(root.pages, pages.init_root, label="init_root") >> Perform(
                ref,
                first_paint,
                label="first_paint",
            )

            body = (
                ops.dispatch(base, ref, view)
                | ship.watch(ref, root, view)
                | ship.tree(ref, view)
                | ship.page(ref, view)
                | ship.status(ref, view)
            )

            try:
                await nu.arun(boot >> body, ctx)  # type: ignore[arg-type]
            finally:
                await view.dispose()

        return athunk
