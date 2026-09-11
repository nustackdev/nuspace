"""The Lens op table: one wire path per op, one body per path.

    op     payload
    --     --
    nav    {path}

One op, and the table is still worth having. It is where the browser and
the server agree on a name, it is what ``stray`` measures a stale call
site against, and it is the place a second op lands the day the lens
grows one -- a pinned column, a refresh, a cap bump.

``target`` is the Ref the op's effect lands on. ``nav`` writes nothing:
its whole effect is a frame back to this connection, so it names the
surface ref. A Command's mutation slot is an address, and that is the
honest one here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.refs.common import Ops


if TYPE_CHECKING:
    import nu
    from nuspace.web.refs.lens.ref import LensRef
    from nuspace.web.refs.lens.view import View


__all__ = ["dispatch"]


def dispatch(base: str, ref: LensRef, view: View) -> nu.Nu:
    """Build the reactive handler for every op, composed in parallel."""
    ops = Ops(base)
    return ops.on("nav", ref, view.navigate) | ops.stray(ref)
