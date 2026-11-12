"""Everything the desks node says and hears, in the browser's own words.

- **Events**, browser to host. One path per op under ``<desks>.ops.``.
- **Writes**, host to browser. Three, on the node's own path, tagged with an
  ``op`` key. Each replaces what the browser held: no deltas.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`. Desk ids are minted by the browser: ``desk.create`` carries
the id of the desk being created.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import DictArg, ListArg, Nu
    from nustd.ui.core import Changed, Ref


__all__ = [
    "on_create_desk",
    "on_delete_desk",
    "on_move_desk",
    "on_rename_desk",
    "on_set_role",
    "on_write_items",
    "set_desks",
    "set_roles",
    "set_titles",
]


# --- Writes: host -> browser --------------------------------------------------


def set_desks(desks: Ref, held: DictArg, order: ListArg[str]) -> Nu:
    """Replace every desk: ``{desk_id: {name, items}}``, each desk whole, and ``order``, their ids in sidebar order."""
    return write(desks, "set_desks", desks=held, order=order)


def set_roles(desks: Ref, roles: DictArg) -> Nu:
    """Replace the roles: ``{home, settings, search}``, each a plane id."""
    return write(desks, "set_roles", roles=roles)


def set_titles(desks: Ref, titles: DictArg) -> Nu:
    """Replace the looks of the planes any desk links to: ``{plane_id: {title, icon}}``."""
    return write(desks, "set_titles", titles=titles)


# --- Events: browser -> host --------------------------------------------------


def on_create_desk(desks: Ref) -> Changed:
    """``{desk_id, desk}``, ``desk`` as ``{name, items}``, last among the desks. The browser minted ``desk_id``."""
    return event(desks, "desk.create")


def on_rename_desk(desks: Ref) -> Changed:
    """``{desk_id, name}``."""
    return event(desks, "desk.rename")


def on_write_items(desks: Ref) -> Changed:
    """``{writes: [{desk_id, sets, deletes, order}]}``: item writes on one desk or more, as one commit.

    ``sets`` item id to item (no id in it), ``deletes`` and ``order`` item
    ids. A move across desks is one event: a delete on one desk, a set on
    the other.
    """
    return event(desks, "items.write")


def on_delete_desk(desks: Ref) -> Changed:
    """``{desk_id}``."""
    return event(desks, "desk.delete")


def on_move_desk(desks: Ref) -> Changed:
    """``{desk_id, before}``. ``before`` the desk it goes in front of, ``""`` for last."""
    return event(desks, "desk.move")


def on_set_role(desks: Ref) -> Changed:
    """``{role, plane_id}``. Sets or changes a role, there is no remove."""
    return event(desks, "role.set")
