"""The desks feed: one arm per interaction, all in parallel, for one tab. Host only.

- **browser to store.** A desk event runs one op over its own fields, in
  its own Web commit. A failure toasts on the tab
  (:meth:`~nuspace.web.utils.Arms.event`).
- **store to browser.** The desks changed (any desk created, set, moved
  or deleted, by any tab or program): every desk ships again, whole, in
  creation order, with that order as a list. The roles changed: the roles
  ship again. A desk is a few hundred bytes, so shipping all of them is
  cheaper than tracking which one moved. A desk not on the desk shape (one
  stored in an older shape) is left out.
- **titles.** The title and icon of every plane a desk links to, original
  or recent, ship as their own write, so a tab names an item it neither
  has open nor sees in its lazy tree. They ship again when the desks
  change and when a plane's name or icon changes, the watches the
  sidebar's tree uses. A plane with no row, or removed, is left out.

Level, with no re-checks, as the sidebar: a missed notification leaves
the tab stale until the next change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace.ops.brackets import atomic
from nuspace.shapes.space import Space
from nuspace.web import ops as web
from nuspace.web.desks import interactions
from nuspace.web.desks import ops as desk_ops
from nuspace.web.desks.model import DeskPlanes, ShapedDesks
from nuspace.web.shapes import Web
from nuspace.web.utils import Arms, field_dict, field_str


if TYPE_CHECKING:
    from collections.abc import Callable

    from nustd.ui.core import Ref


__all__ = ["desks_feed", "titles"]


def _ship(read: nu.Nu, send: Callable[[nu.Dict], nu.Nu]) -> nu.Nu:
    """``read`` in one snapshot, then ``send(value)`` to the browser."""
    return nu.let(atomic(read), lambda held: send(nu.Dict(held)))


def titles() -> nu.Dict:
    """``{plane_id: {title, icon}}`` for every plane a desk links to, original or recent. Bare read.

    A title or icon the plane lacks is ``""``. A plane with no row, or
    removed, is left out. Cost: one read of the desks, four reads a plane
    on them.
    """

    def look(at: nu.Attr) -> nu.List:
        plane = nu.Str(at)
        row = Space.planes[plane]
        return nu.List.of(
            plane, nu.Dict.of(title=row.name.fallback(""), icon=row.icon.fallback(""))
        )

    planes = nu.List(DeskPlanes(Web.desks.extract()))
    shown = planes.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p)))
    return nu.dict(shown.map(look).to_list())


def desks_feed(desks: Ref, toasts: Ref) -> nu.Nu:
    """The desks, the roles and the desk planes' titles of one tab, live, as one term. Built per tab, never ends.

    Args:
        desks: The shell's desks ref.
        toasts: The tab's toast ref, where a failed event shows.
    """
    arms = Arms("desks", toasts)

    def desk(name: str, change: nu.Nu, op: Callable[[nu.Str, nu.Attr], nu.Nu]) -> nu.Nu:
        return arms.event(name, change, lambda ev: atomic(op(field_str(ev, "desk_id"), ev)))

    def role(ev: nu.Attr) -> nu.Nu:
        return atomic(web.set_role(field_str(ev, "role"), field_str(ev, "plane_id")))

    shown = ShapedDesks(Web.desks.extract(), desk_ops.desk_order())

    def send_desks(held: nu.Dict) -> nu.Nu:
        return interactions.set_desks(desks, held, nu.list(held.keys()))

    shipped_desks = _ship(shown, send_desks)
    shipped_roles = _ship(Web.roles.extract(), lambda r: interactions.set_roles(desks, r))
    shipped_titles = _ship(titles(), lambda t: interactions.set_titles(desks, t))
    on_desks = [
        atomic(Web.desks.on_children_change()),
        atomic(Web.desks.on_descendants_change("*")),
        atomic(Web.desk_order.on_children_change()),
    ]
    return nu.ParallelAsync(
        arms.states("desks", on_desks, shipped_desks),
        arms.states(
            "roles",
            [atomic(Web.roles.on_children_change()), atomic(Web.roles.on_descendants_change("*"))],
            shipped_roles,
        ),
        arms.states(
            "titles",
            [
                *on_desks,
                atomic(Space.planes.on_descendants_change("*", "name")),
                atomic(Space.planes.on_descendants_change("*", "icon")),
            ],
            shipped_titles,
        ),
        desk(
            "create",
            interactions.on_create_desk(desks),
            lambda d, ev: desk_ops.create_desk(d, field_dict(ev, "desk")),
        ),
        desk(
            "set",
            interactions.on_set_desk(desks),
            lambda d, ev: desk_ops.set_desk(d, field_dict(ev, "desk")),
        ),
        desk("delete", interactions.on_delete_desk(desks), lambda d, _: desk_ops.delete_desk(d)),
        desk(
            "move",
            interactions.on_move_desk(desks),
            lambda d, ev: desk_ops.move_desk(d, field_str(ev, "before")),
        ),
        arms.event("role", interactions.on_set_role(desks), role),
    )
