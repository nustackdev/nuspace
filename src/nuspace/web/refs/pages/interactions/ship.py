"""Shipping: three outbound loops and the one subscription that feeds them.

Each loop is the same three-atom composition:

    nu.ForeverDo(nu.ui.Write(ref, Payload(build)))

``Write`` is nu's. It resolves the ref's wire path and sends the frame;
nuspace used to reimplement it once per surface. What stays ours is
``Payload``, which is a different thing: a Query that computes what to
ship. The split is the point -- the framing is nu's, the content is the
surface's.

Each ``build`` blocks until its payload is stale, so a loop that has
nothing to say costs nothing and never spins.

``watch`` is the subscription all three hang off. ``Space.pages`` is a
``PrefixFilter``, depth-unbounded, so one subscription covers the whole
recursive page tree -- every page, every child page, every block, every
slot. The driver used to reship by hand after each of its own writes,
which is why a page another connection added stayed invisible. It does
not any more: the write and the paint are decoupled by the substrate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.ui
from nu.kv.tree import auto_flow_atomic
from nuspace.web.refs.common import Payload, Perform


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nuspace.web.refs.pages.ref import PagesRef
    from nuspace.web.refs.pages.view import View


__all__ = ["page", "status", "tree", "watch"]


def tree(ref: PagesRef, view: View) -> nu.Nu:
    """Paint the page rail whenever the page tree changes."""
    return nu.ForeverDo(nu.ui.Write(ref, Payload(view.next_tree, label="tree")))


def page(ref: PagesRef, view: View) -> nu.Nu:
    """Paint the block canvas, then start what the paint planned.

    Two steps, in this order, because frames are ordered on the ws: the
    browser registers the block's field slices from the payload before
    the section that writes to them exists. ``launch`` is a no-op when
    the last plan queued nothing, which is the common case.
    """
    return nu.ForeverDo(
        nu.ui.Write(ref, Payload(view.next_page, label="page"))
        >> Perform(ref, view.launch, label="launch"),
    )


def status(ref: PagesRef, view: View) -> nu.Nu:
    """Relay section status, one frame per burst."""
    return nu.ForeverDo(nu.ui.Write(ref, Payload(view.next_status, label="status")))


def watch(ref: PagesRef, root: type[Shape], view: View) -> nu.Nu:
    """Mark both payloads stale on any write under ``Space.pages``.

    The body only marks; the loops do the reading. That matters because
    notifications are per key rather than per logical op -- deleting a
    page with four sections fires eleven of them -- and a body that
    shipped would ship eleven times.

    ``invalidate``'s effect lands on the surface ref, not on kv: it does
    not write the document, it says this connection's picture of it is
    out of date. That is also what keeps the body out of a transaction.

    The ``auto_flow_atomic`` pass is what gives ``on_change`` a snapshot
    to resolve its address against. It brackets the subscription slot
    only -- ``ReactForever`` is a Flow, so the pass places the bracket on
    its children rather than around the loop, and a forever loop never
    sits inside an open handle.
    """
    return auto_flow_atomic(
        nu.ReactForever(
            root.pages.on_change(),
            Perform(
                ref,
                view.invalidate,
                args="nuspace.pages.key",
                splat=False,
                label="invalidate",
            ),
            changed_key="nuspace.pages.key",
        ),
        scope=root,
    )
