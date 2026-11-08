"""Everything the sidebar says and hears, in the browser's own words.

- **Events**, browser to host. One path per op under ``<sidebar>.ops.``.
- **Writes**, host to browser. One, on the sidebar's own path, tagged with
  an ``op`` key.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`. Ids are minted by the browser: ``plane.create`` carries the id
of the plane being created.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.devices.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu
    from nustd.ui.core import Changed, Ref


__all__ = [
    "KINDS",
    "KIND_PLANE",
    "KIND_SPACE",
    "ROOT_ID",
    "on_collapse",
    "on_create_plane",
    "on_delete_plane",
    "on_expand",
    "on_move_pin",
    "on_move_plane",
    "on_pin_plane",
    "on_rename_plane",
    "on_set_icon",
    "on_unpin_plane",
    "set_tree",
]


#: The one row that stands for the space. Nobody stored it, nothing opens it.
KIND_SPACE = "space"

#: A plane. The only row that is in the store and the only one that opens.
KIND_PLANE = "plane"

#: Every kind a row can be, said on every row rather than guessed from an id.
KINDS = (KIND_SPACE, KIND_PLANE)

#: The space row's id, and its own parent: the browser takes the first self
#: parenting row as the root. Top level planes hang under it. A word, never a
#: minted id, and the browser's name for the store's top level.
ROOT_ID = "space"


# --- Writes: host -> browser --------------------------------------------------


def set_tree(sidebar: Ref, rows: ListArg[dict], pinned: ListArg[str]) -> Nu:
    """Replace the sidebar. A row is ``{id, kind, title, parent, children, spec, icon, system}``.

    The tree is lazy: ``children`` is filled only for the space row and the
    branches the tab has open; every other row ships ``[]``. ``pinned`` is
    the pinned plane ids, in order, every one a row too.
    """
    return write(sidebar, "set_tree", planes=rows, pinned=pinned)


# --- Events: browser -> host --------------------------------------------------


def on_create_plane(sidebar: Ref) -> Changed:
    """``{plane_id, parent_id, spec, title}``. The browser minted ``plane_id``.

    ``spec`` names the registered PlaneSpec to create, ``""`` for the empty
    plane; ``parent_id`` is a plane id or :data:`ROOT_ID`.
    """
    return event(sidebar, "plane.create")


def on_rename_plane(sidebar: Ref) -> Changed:
    """``{plane_id, title}``."""
    return event(sidebar, "plane.rename")


def on_delete_plane(sidebar: Ref) -> Changed:
    """``{plane_id}``."""
    return event(sidebar, "plane.delete")


def on_move_plane(sidebar: Ref) -> Changed:
    """``{plane_id, parent_id, before?, after?}``.

    ``before`` or ``after`` is a sibling under ``parent_id``, neither the end.
    """
    return event(sidebar, "plane.move")


def on_set_icon(sidebar: Ref) -> Changed:
    """``{plane_id, icon}``. ``icon`` is ``lucide:<name>``, ``emoji:<char>`` or ``""``."""
    return event(sidebar, "plane.icon")


def on_pin_plane(sidebar: Ref) -> Changed:
    """``{plane_id, before?, after?}``: pin before or after a pin, neither the end."""
    return event(sidebar, "plane.pin")


def on_unpin_plane(sidebar: Ref) -> Changed:
    """``{plane_id}``. The plane stays in the tree."""
    return event(sidebar, "plane.unpin")


def on_move_pin(sidebar: Ref) -> Changed:
    """``{plane_id, before?, after?}``. Moves a pinned plane, placed as in ``plane.pin``."""
    return event(sidebar, "plane.pin_move")


def on_expand(sidebar: Ref) -> Changed:
    """``{plane_id}``. The tab opened the branch: its children load."""
    return event(sidebar, "plane.expand")


def on_collapse(sidebar: Ref) -> Changed:
    """``{plane_id}``. The tab closed the branch."""
    return event(sidebar, "plane.collapse")
