"""Everything the sidebar says and hears, in the browser's own words.

Two halves, and every name here is the spelling on the wire rather than the one
in the model. A Plane is a ``page`` to the browser, because the browser was
written against that word and moving it to the model's is a deliberate move of
its own, made later.

- **Events**, browser to server. One subscription per op, each on a path of its
  own under ``<sidebar>.ops.``. The path is the discrimination, so a driver
  binds one arm per op instead of switching on a string in a payload, and a
  browser that spells an op wrong notifies into a path nobody listens on rather
  than into somebody else's handler.
- **Writes**, server to browser. One of them, on the sidebar's own path and
  tagged with an ``op`` key, because the browser registers one handler per node
  and a write to a path with no handler is dropped.

Nothing here reads or writes a store. What an event means is
:mod:`nuspace.ops`, and which op is wired to which arm is
:mod:`nuspace.web.sidebar.driver`.

**Ids are minted by the browser.** ``page.create`` carries the id of the Plane
being made, so a create is a pure function of its event: re-running an arm
rewrites one row instead of adding a second, and the browser routes to what it
just made without waiting to be told its name.

Opening a Plane is not here. The sidebar moves the browser's URL and the Viewer
is what says a Plane was selected, so ``page.select`` is the Viewer's op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.web.utils import event, write


if TYPE_CHECKING:
    from nu.lang import ListArg, Nu
    from nustd.ui.core import Changed, Ref


__all__ = [
    "on_create_plane",
    "on_delete_plane",
    "on_move_plane",
    "on_rename_plane",
    "on_reorder_planes",
    "set_tree",
]


# --- writes: server -> browser ----------------------------------------------


def set_tree(sidebar: Ref, planes: ListArg[dict]) -> Nu:
    """Replace the sidebar: every Plane that draws, flat.

    A row is ``{id, title, parent, children}``, and exactly one of them has to
    name itself as its own parent or the browser finds no root and the sidebar
    stays a row of skeletons forever.
    """
    return write(sidebar, "set_tree", pages=planes)


# --- events: browser -> server ----------------------------------------------


def on_create_plane(sidebar: Ref) -> Changed:
    """``{page_id, parent_id, title}``. The browser minted ``page_id``."""
    return event(sidebar, "page.create")


def on_rename_plane(sidebar: Ref) -> Changed:
    """``{page_id, title}``."""
    return event(sidebar, "page.rename")


def on_delete_plane(sidebar: Ref) -> Changed:
    """``{page_id}``."""
    return event(sidebar, "page.delete")


def on_move_plane(sidebar: Ref) -> Changed:
    """``{page_id, parent_id, index}``. Reparent, landing at ``index``."""
    return event(sidebar, "page.move")


def on_reorder_planes(sidebar: Ref) -> Changed:
    """``{parent_id, page_ids}``. One parent's children, in the new order."""
    return event(sidebar, "page.reorder")
