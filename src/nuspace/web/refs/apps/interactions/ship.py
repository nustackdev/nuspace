"""Shipping: two outbound loops and the one subscription that feeds them.

Each loop is the same composition:

    nu.ForeverDo(nu.ui.Write(ref, Payload(build)))

``Write`` is nu's. It resolves the ref's wire path and sends the frame.
What stays ours is ``Payload``, a Query that computes what to ship. The
framing is nu's, the content is the surface's.

Each ``build`` blocks until its payload is stale, so a loop that has
nothing to say costs nothing and never spins.

Two loops rather than Pages' three, and the missing one is the point: an
app is headless, so there is no canvas to paint. The list carries the
source and the status, and that is everything an app surface can honestly
show.

``watch`` is the subscription the list loop hangs off. ``Space.apps`` is
a ``PrefixFilter``, depth-unbounded, so one subscription covers every app
and every slot on it. The driver used to reship by hand after each of its
own writes, which is why an app another connection added stayed invisible
until you reloaded. It does not any more.

Status does not go through ``watch``, and cannot: an app's status is not
in kv. It comes off the space-lifetime runtime through
``View.observe``'s listener into the ``StatusRelay``, which is why apps
status is observed for real rather than only reported at paint time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.ui
from nu.kv.tree import auto_flow_atomic
from nuspace.web.refs.common import Payload, Perform


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nuspace.web.refs.apps.ref import AppsRef
    from nuspace.web.refs.apps.view import View


__all__ = ["apps", "status", "watch"]


def apps(ref: AppsRef, view: View) -> nu.Nu:
    """Paint the app rail whenever the app list changes."""
    return nu.ForeverDo(nu.ui.Write(ref, Payload(view.next_apps, label="apps")))


def status(ref: AppsRef, view: View) -> nu.Nu:
    """Relay app status, one frame per burst."""
    return nu.ForeverDo(nu.ui.Write(ref, Payload(view.next_status, label="status")))


def watch(ref: AppsRef, root: type[Shape], view: View) -> nu.Nu:
    """Mark the app list stale on any write under ``Space.apps``.

    The body only marks; the loop does the reading. That matters because
    notifications are per key rather than per logical op -- one
    ``set_item`` fires one per slot on the app -- and a body that shipped
    would ship each time.

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
            root.apps.on_change(),
            Perform(
                ref,
                view.invalidate,
                args="nuspace.apps.key",
                splat=False,
                label="invalidate",
            ),
            changed_key="nuspace.apps.key",
        ),
        scope=root,
    )
