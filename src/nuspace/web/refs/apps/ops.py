"""The Apps op table: one wire path per op, one body per path.

The browser notifies ``<apps ref>.ops.<name>`` and the payload carries
that op's arguments and nothing else. There is no ``op`` key, because the
path already answered that question.

    op             payload
    --             --
    app.create     {name, source?}
    app.rename     {app_id, name}
    app.delete     {app_id}
    app.update     {app_id, source}
    app.restart    {app_id}

There is no ``app.select``: selection is the URL.

``target`` is the Ref each op's effect lands on. The four that change the
app list name ``Space.apps``; ``app.restart`` writes no kv at all and
only moves what this space is running, so it names the surface ref. A
Command's mutation slot is an address, and these are the honest ones.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.refs.apps.interactions import AppOps
from nuspace.web.refs.common import Ops


if TYPE_CHECKING:
    import nu
    from nuspace.web.refs.apps.ref import AppsRef
    from nuspace.web.refs.apps.view import View


__all__ = ["dispatch"]


def dispatch(base: str, ref: AppsRef, view: View) -> nu.Nu:
    """Build the reactive handler for every op, composed in parallel."""
    ops = Ops(base)
    app = AppOps(view)
    kv = view.root.apps

    handlers = [
        ops.on("app.create", kv, app.create),
        ops.on("app.rename", kv, app.rename),
        ops.on("app.delete", kv, app.delete),
        ops.on("app.update", kv, app.update),
        ops.on("app.restart", ref, app.restart),
        ops.stray(ref),
    ]
    composed = handlers[0]
    for handler in handlers[1:]:
        composed = composed | handler
    return composed
