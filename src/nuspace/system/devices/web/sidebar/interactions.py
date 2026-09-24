"""Everything the sidebar says and hears, in the browser's own words.

Every name here is the wire spelling, not the model's: a plane is a ``page``
to the browser.

- **Events**, browser to host. One path per op under ``<sidebar>.ops.``.
- **Writes**, host to browser. One, on the sidebar's own path, tagged with
  an ``op`` key.

Nothing here reads or writes a store. Which op an event runs is
:mod:`.feed`. Ids are minted by the browser: ``page.create`` carries the id
of the plane being made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.system.devices.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu
    from nustd.ui.core import Changed, Ref


__all__ = [
    "KINDS",
    "KIND_GROUP",
    "KIND_PLANE",
    "KIND_SPACE",
    "ROOT_ID",
    "on_create_plane",
    "on_delete_plane",
    "on_move_plane",
    "on_rename_plane",
    "on_reorder_planes",
    "set_tree",
]


#: The one row that stands for the space. Nobody stored it, nothing opens it.
KIND_SPACE = "space"

#: A section: one per app that declares one. Holds the planes it made.
KIND_GROUP = "group"

#: A plane. The only row that is in the store and the only one that opens.
KIND_PLANE = "plane"

#: Every kind a row can be, said on every row rather than guessed from an id.
KINDS = (KIND_SPACE, KIND_GROUP, KIND_PLANE)

#: The row every section hangs under, and its own parent: the browser takes
#: the first self parenting row as the root. A word, never a minted id.
ROOT_ID = "space"


# --- Writes: host -> browser --------------------------------------------------


def set_tree(sidebar: Ref, rows: ListArg[dict]) -> Nu:
    """Replace the sidebar. A row is ``{id, kind, title, parent, children}``."""
    return write(sidebar, "set_tree", pages=rows)


# --- Events: browser -> host --------------------------------------------------


def on_create_plane(sidebar: Ref) -> Changed:
    """``{page_id, parent_id, group, title}``. The browser minted ``page_id``."""
    return event(sidebar, "page.create")


def on_rename_plane(sidebar: Ref) -> Changed:
    """``{page_id, title}``."""
    return event(sidebar, "page.rename")


def on_delete_plane(sidebar: Ref) -> Changed:
    """``{page_id}``."""
    return event(sidebar, "page.delete")


def on_move_plane(sidebar: Ref) -> Changed:
    """``{page_id, parent_id, index}``. Not wired yet."""
    return event(sidebar, "page.move")


def on_reorder_planes(sidebar: Ref) -> Changed:
    """``{parent_id, page_ids}``. Not wired yet."""
    return event(sidebar, "page.reorder")
