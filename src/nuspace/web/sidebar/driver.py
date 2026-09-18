"""The sidebar, live: one arm per interaction, all in parallel.

Flat on purpose. Every arm is one subscription wired to one thing, and there is
no dispatch anywhere in it. Two families, and an arm belongs to exactly one:

- **browser to store.** A sidebar event fires; the arm runs one
  :mod:`nuspace.ops` call over the event's own fields.
- **store to browser.** The Planes changed; the arm ships the list again.

**The synthetic root.** The browser renders a tree off ``parent`` and
``children`` and a Plane has neither, because a Space is one flat container and
a relation between two Planes is a field rather than storage depth. So the list
ships as one row nobody stored, carrying every listed Plane as a child. The
shim is here and goes no further: nothing in :mod:`nuspace.shapes` knows about
it, the root's id is a Plane id nobody could mint, and every op addressed at it
is a no-op because no Plane is there.

Which Plane this connection has open is :mod:`nuspace.web.route`, and drawing
one is :mod:`nuspace.web.viewer`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import EXEC_ASYNC, TRIGGER_NAV, Space
from nuspace.web.sidebar import interactions
from nuspace.web.utils import Arms, field_str


if TYPE_CHECKING:
    from nuspace.web.sidebar.ref import SidebarRef


__all__ = ["ARMS", "ROOT_ID", "rows", "sidebar_driver"]


#: How many arms the composition folds. Pinned so an interaction that forgets
#: its arm, or an arm that quietly loses its subscription, says so.
ARMS = 4


#: The row every Plane hangs under. Not a Plane and never stored: the browser
#: needs exactly one row that names itself as its own parent or it finds no root
#: and the sidebar stays a row of skeletons. A word rather than a minted id, so
#: a real Plane can never collide with it.
ROOT_ID = "space"

#: Every arm in this module, labelled for the reports it prints.
_arms = Arms("sidebar")

#: What the filter binds the Plane it is deciding about under, and what the row
#: builder binds the Plane it is describing under. Two of them because they are
#: two questions, and both named for this module because every arm on a
#: connection shares one ``ctx.attrs`` and ``item`` is a name anything could be
#: standing on.
_PICK = "_sidebar_pick"
_ROW = "_sidebar_row"
_pick = nu.DictAttrRef(_PICK)
_row = nu.DictAttrRef(_ROW)


def _listed(root: type[Space]) -> nu.Nu:
    """The Planes the sidebar lists, in creation order.

    Built fresh at each call site. One node in two tree positions is one node,
    and this one is read twice per answer: once for the ids the root row
    carries, once for the rows themselves.
    """
    return nu.List(
        nu.Collect(
            nu.Filter(
                ops.plane_rows(root=root),
                nu.ToBool(_pick.get_item(nu.Str("ui"), nu.Bool(False))),
                key=_PICK,
            )
        )
    )


def _ids(root: type[Space]) -> nu.Nu:
    """The ids of the listed Planes, which is the order the sidebar draws them in.

    The browser walks the root row's ``children`` and skips an id the list does
    not hold, so a Plane missing from here never appears whatever else it
    carries.
    """
    return nu.List(
        nu.Collect(
            nu.Map(
                _listed(root),
                nu.ToStr(_row.get_item(nu.Str("id"), nu.Str(""))),
                key=_ROW,
            )
        )
    )


def rows(*, root: type[Space] = Space) -> nu.Nu:
    """Every Plane that draws as a browser row, under one root row nobody stored.

    ``parent`` is written on every row and never left out. The browser defaults
    a row's parent to the row's own id and takes the first self-parenting row as
    the root, so a Plane row that forgot its parent would become the root and
    the sidebar would render one item.
    """
    space = nu.Dict.of(
        id=nu.Str(ROOT_ID),
        # Empty, and the browser draws its own word for the Space in its place.
        # The row is not a Plane, so there is no name to give it.
        title=nu.Str(""),
        parent=nu.Str(ROOT_ID),
        children=_ids(root),
    )
    listed = nu.Collect(
        nu.Map(
            _listed(root),
            nu.Dict.of(
                id=nu.ToStr(_row.get_item(nu.Str("id"), nu.Str(""))),
                title=nu.ToStr(_row.get_item(nu.Str("name"), nu.Str(""))),
                parent=nu.Str(ROOT_ID),
                # Planes do not nest yet, so the hierarchy is one level deep and
                # every Plane is a leaf of the row that stands for the Space.
                children=nu.List.of(),
            ),
            key=_ROW,
        )
    )
    return nu.List.of(space) + nu.List(listed)


def sidebar_driver(sidebar: SidebarRef, *, root: type[Space] = Space) -> nu.Nu:
    """The sidebar, live, as one tree. Built per connection.

    Args:
        sidebar: the :class:`~nuspace.web.sidebar.ref.SidebarRef` on the shell,
            already bound to its slot so its chain resolves.
        root: the Space shape class.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never finishes.
    """
    listing = rows(root=root)
    # Shipped unprompted, because nothing can be selected until the sidebar
    # knows what a root is.
    boot = interactions.set_tree(sidebar, listing)

    flow = (
        # -- browser -> store ---------------------------------------------------
        # A Plane made from the sidebar is a page somebody writes: one process
        # for the whole Plane, up while somebody is looking at it, drawn, and
        # authored from inside the Viewer.
        _arms.event(
            "create_plane",
            interactions.on_create_plane(sidebar),
            ops.add_plane(
                plane_id=field_str("create_plane", "page_id"),
                name=field_str("create_plane", "title"),
                exec_mode=EXEC_ASYNC,
                trigger=TRIGGER_NAV,
                ui=True,
                editable=True,
                root=root,
            ),
        )
        | _arms.event(
            "rename_plane",
            interactions.on_rename_plane(sidebar),
            ops.rename_plane(
                field_str("rename_plane", "page_id"),
                field_str("rename_plane", "title"),
                root=root,
            ),
        )
        | _arms.event(
            "delete_plane",
            interactions.on_delete_plane(sidebar),
            ops.remove_plane(field_str("delete_plane", "page_id"), root=root),
        )
        # -- store -> browser ---------------------------------------------------
        # One fresh subscription, never a term shared with another arm: two arms
        # holding one node would hold one handle, and the first of them to end
        # would close it under the other.
        | _arms.state(
            "tree",
            root.planes.on_change(),
            interactions.set_tree(sidebar, rows(root=root)),
        )
    )
    return nustd.kv.auto_flow_atomic(boot >> flow, scope=root)
