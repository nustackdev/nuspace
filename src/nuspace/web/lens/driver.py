"""The lens driver: one ``ReactForever`` arm, and a boot frame beside it.

Flat like the other two, and shorter, because the surface is read-only. There
is one interaction -- the browser moved its cursor -- so there is one arm, and
nothing in it branches: no ``op`` string to switch on, no table of handlers,
no python callable smuggled into an atom.

One family only, **browser -> browser**. The arm hears a path, reads whatever
kv the walk to that path touches, and ships the columns back. It writes
nothing, so there is no kv -> browser half and no subscription on a container:
the design is a snapshot per navigation, and a store that moves under a
standing cursor is v2's problem (see ``lens.md``).

The boot frame is the root column, and it is built at construct time rather
than through :func:`~nuspace.web.lens.reflect.columns`: the empty path is the
one path that is known before the browser says anything.

**Every arm is long-lived by construction.** The ws endpoint races the
connection against this tree and closes the socket when either finishes, so a
tree that completes drops the browser. What keeps that true -- the double
guard, the per-arm attrs namespace, the fresh subscription -- is
:mod:`nuspace.web.arms`, shared with the other two drivers. The arm name is
prefixed ``lens_`` so a composition holding all three cannot have two arms
binding one attrs key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
from nuspace._root import resolve_root
from nuspace.web.arms import Arms, field_ids
from nuspace.web.lens.reflect import DEFAULT_MAX_ROWS, column_terms, columns


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nuspace.web.lens.ref import LensRef


__all__ = ["ARMS", "lens_driver"]


#: How many arms the composition folds. Pinned so a new interaction that
#: forgets its arm, or an arm that quietly loses its subscription, says so.
ARMS = 1


#: Every arm in this module, labelled for the reports it prints.
_arms = Arms("lens")


#: This arm's attrs namespace, and what a failure is reported as.
_NAV = "lens_nav"


def lens_driver(
    lens: LensRef,
    *,
    root: type[Shape] | None = None,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> nu.Nu:
    """The lens surface, live, as one tree. Built per connection.

    Args:
        lens: the ``LensRef`` on the mounted shell, already bound to its
            screen so its wire path resolves.
        root: the Shape class the lens browses. The space's own root by
            default, which is what the stock shell mounts.
        max_rows: the per-column cap. The same number the ref put in its
            mount props, so the browser's ``n/total`` note agrees with what
            was actually clipped.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never
        finishes, which is the contract the ws endpoint holds it to.
    """
    root = resolve_root(root)

    # The root column, settled here: an empty path names no runtime segment,
    # so the walk is ordinary python over the Shape class and needs no Eval.
    # The browser paints on the first frame instead of on the first click.
    boot = lens.set_columns(nu.List.of(), column_terms(root, (), max_rows))

    flow = _arms.event(
        _NAV,
        lens.on_nav(),
        # Two fresh reads of the same field, never one term in two positions:
        # a Nu node is a value, and one object sitting in two tree positions
        # is one compiled node the two of them then share at runtime.
        lens.set_columns(
            field_ids(_NAV, "path"),
            columns(root, field_ids(_NAV, "path"), max_rows=max_rows),
        ),
    )
    return nu.kv.auto_flow_atomic(boot >> flow, scope=root)
