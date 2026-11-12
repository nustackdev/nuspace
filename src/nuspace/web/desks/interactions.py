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
    "on_set_desk",
    "on_set_role",
    "set_desks",
    "set_roles",
    "set_titles",
]


# --- Writes: host -> browser --------------------------------------------------


def set_desks(desks: Ref, held: DictArg, order: ListArg[str]) -> Nu:
    """Replace every desk: ``{desk_id: desk}``, each desk the whole dict, and ``order``, their ids in creation order."""
    return write(desks, "set_desks", desks=held, order=order)


def set_roles(desks: Ref, roles: DictArg) -> Nu:
    """Replace the roles: ``{home, settings, search}``, each a plane id."""
    return write(desks, "set_roles", roles=roles)


def set_titles(desks: Ref, titles: DictArg) -> Nu:
    """Replace the looks of the planes any desk links to: ``{plane_id: {title, icon}}``."""
    return write(desks, "set_titles", titles=titles)


# --- Events: browser -> host --------------------------------------------------


def on_create_desk(desks: Ref) -> Changed:
    """``{desk_id, desk}``. The browser minted ``desk_id``."""
    return event(desks, "desk.create")


def on_set_desk(desks: Ref) -> Changed:
    """``{desk_id, desk}``. The desk whole, last write wins."""
    return event(desks, "desk.set")


def on_delete_desk(desks: Ref) -> Changed:
    """``{desk_id}``."""
    return event(desks, "desk.delete")


def on_move_desk(desks: Ref) -> Changed:
    """``{desk_id, before}``. ``before`` the desk it goes in front of, ``""`` for last."""
    return event(desks, "desk.move")


def on_set_role(desks: Ref) -> Changed:
    """``{role, plane_id}``. Sets or changes a role, there is no remove."""
    return event(desks, "role.set")
