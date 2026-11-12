"""The desks feed: one arm per interaction, all in parallel, for one tab. Host only.

- **browser to store.** A desk event runs its ops in one Web commit: a
  create, a rename, a delete, a move, or ``items.write``, item writes on
  one desk or more (a move across desks is one of these). A failure toasts
  on the tab (:meth:`~nuspace.web.utils.Arms.event`) and writes nothing.
- **store to browser.** Any desk write (a desk created, renamed, moved or
  deleted, an item set, moved or taken off, by any tab or program): every
  desk ships again, whole, read back as ``{name, items}``, in sidebar
  order, with that order as a list. A desk is a few hundred bytes, so
  shipping all of them is cheaper than tracking which one moved. The roles
  changed: the roles ship again.
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
from nuspace.web.desks.model import DeskPlanes, DesksView, Items
from nuspace.web.shapes import Web
from nuspace.web.utils import Arms, field_dict, field_dicts, field_str


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


def _create(ev: nu.Attr) -> nu.Nu:
    """``desk.create``: the desk, last, then its items in their order."""
    desk_id = field_str(ev, "desk_id")
    desk = field_dict(ev, "desk")
    made = desk_ops.create_desk(nu.Str(desk["name"]), id=desk_id)
    return made >> desk_ops.write_items(desk_id, Items(desk["items"]))


def _move(ev: nu.Attr) -> nu.Nu:
    """``desk.move``: in front of ``before``, last for ``""``."""
    desk_id, before = field_str(ev, "desk_id"), field_str(ev, "before")
    return nu.IfDo(
        before == "", desk_ops.move_desk(desk_id), desk_ops.move_desk(desk_id, before=before)
    )


def _write(ev: nu.Attr) -> nu.Nu:
    """``items.write``: each desk's writes in turn, the caller's one commit around them all."""

    def one(held: nu.Attr) -> nu.Nu:
        w = nu.Dict(held)
        return desk_ops.write_items(nu.Str(w["desk_id"]), w["sets"], w["deletes"], w["order"])

    return nu.ForEachDo(field_dicts(ev, "writes"), one)


def desks_feed(desks: Ref, toasts: Ref) -> nu.Nu:
    """The desks, the roles and the desk planes' titles of one tab, live, as one term. Built per tab, never ends.

    Args:
        desks: The shell's desks ref.
        toasts: The tab's toast ref, where a failed event shows.
    """
    arms = Arms("desks", toasts)

    def op(name: str, change: nu.Nu, run: Callable[[nu.Attr], nu.Nu]) -> nu.Nu:
        return arms.event(name, change, lambda ev: atomic(run(ev)))

    def send_desks(held: nu.Dict) -> nu.Nu:
        return interactions.set_desks(desks, held, nu.list(held.keys()))

    shipped_desks = _ship(DesksView(Web.desks.extract()), send_desks)
    shipped_roles = _ship(Web.roles.extract(), lambda r: interactions.set_roles(desks, r))
    shipped_titles = _ship(titles(), lambda t: interactions.set_titles(desks, t))
    on_desks = atomic(Web.desks.on_change())
    return nu.ParallelAsync(
        arms.states("desks", [on_desks], shipped_desks),
        arms.states(
            "roles",
            [atomic(Web.roles.on_children_change()), atomic(Web.roles.on_descendants_change("*"))],
            shipped_roles,
        ),
        arms.states(
            "titles",
            [
                atomic(Web.desks.on_change()),
                atomic(Space.planes.on_descendants_change("*", "name")),
                atomic(Space.planes.on_descendants_change("*", "icon")),
            ],
            shipped_titles,
        ),
        op("create", interactions.on_create_desk(desks), _create),
        op(
            "rename",
            interactions.on_rename_desk(desks),
            lambda ev: desk_ops.rename_desk(field_str(ev, "desk_id"), field_str(ev, "name")),
        ),
        op(
            "delete",
            interactions.on_delete_desk(desks),
            lambda ev: desk_ops.delete_desk(field_str(ev, "desk_id")),
        ),
        op("move", interactions.on_move_desk(desks), _move),
        op("write", interactions.on_write_items(desks), _write),
        op(
            "role",
            interactions.on_set_role(desks),
            lambda ev: web.set_role(field_str(ev, "role"), field_str(ev, "plane_id")),
        ),
    )
