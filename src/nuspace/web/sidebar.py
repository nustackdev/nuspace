"""The Plane list a tab navigates with, and the one shape it has to be in.

A Plane names its ``viewer`` and the sidebar reads that and nothing else, so a
tab is a group of viewers and a viewer arriving later is a tab over the same
list rather than a branch in here. One tab for now, prose, which is every
Plane the surface in this phase can draw.

**The synthetic root.** The browser renders a tree off ``parent`` and
``children`` and a Plane has neither, because a Space is one flat container
and a relation between two Planes is a field rather than storage depth. So the
list ships as one row nobody stored, carrying every listed Plane as a child.
The shim is here and goes no further: nothing in :mod:`nuspace.shapes` knows
about it, the root's id is a Plane id nobody could mint, and every op
addressed at it is a no-op because no Plane is there.

Which is a list and nothing else. Making, naming and dropping a Plane are the
surface's own interactions and are arms in its driver, and which Plane this
connection has open is :mod:`nuspace.web.nav`.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.shapes import VIEWER_PROSE, Space


__all__ = ["ROOT_ID", "rows"]


#: The row every Plane hangs under. Not a Plane and never stored: the browser
#: needs exactly one row that names itself as its own parent or it finds no
#: root and the rail stays a row of skeletons, and the bare ``/pages`` route
#: resolves to whatever that row's id is. A word rather than a minted id, so a
#: real Plane can never collide with it.
ROOT_ID = "space"

#: What the filter binds the Plane it is deciding about under, and what the row
#: builder binds the Plane it is describing under. Two of them because they are
#: two questions, and both named for this module because every arm on a
#: connection shares one ``ctx.attrs`` and ``item`` is a name anything could be
#: standing on.
_PICK = "_nw_pick"
_ROW = "_nw_row"
_pick = nu.DictAttrRef(_PICK)
_row = nu.DictAttrRef(_ROW)


def _listed(viewer: str, root: type[Space]) -> nu.Nu:
    """The Planes this sidebar lists, in creation order.

    Built fresh at each call site. One node in two tree positions is one node,
    and this one is read twice per answer: once for the ids the root row
    carries, once for the rows themselves.
    """
    return nu.List(
        nu.Collect(
            nu.Filter(
                ops.plane_rows(root=root),
                nu.Eq(nu.ToStr(_pick.get_item(nu.Str("viewer"), nu.Str(""))), nu.Str(viewer)),
                key=_PICK,
            )
        )
    )


def _ids(viewer: str, root: type[Space]) -> nu.Nu:
    """The ids of the listed Planes, which is the order the rail draws them in.

    The browser walks the root row's ``children`` and skips an id the list does
    not hold, so a Plane missing from here never appears whatever else it
    carries.
    """
    return nu.List(
        nu.Collect(
            nu.Map(
                _listed(viewer, root),
                nu.ToStr(_row.get_item(nu.Str("id"), nu.Str(""))),
                key=_ROW,
            )
        )
    )


def rows(*, viewer: str = VIEWER_PROSE, root: type[Space] = Space) -> nu.Nu:
    """Every listed Plane as a browser row, under one root row nobody stored.

    ``parent`` is written on every row and never left out. The browser defaults
    a row's parent to the row's own id and takes the first self-parenting row
    as the root, so a Plane row that forgot its parent would become the root
    and the rail would render one item.

    Args:
        viewer: which Planes this tab claims, read off ``props.viewer``.
        root: the Space shape class.
    """
    space = nu.Dict.of(
        id=nu.Str(ROOT_ID),
        # Empty, and the browser draws its own word for the Space in its
        # place. The row is not a Plane, so there is no name to give it.
        title=nu.Str(""),
        parent=nu.Str(ROOT_ID),
        children=_ids(viewer, root),
    )
    listed = nu.Collect(
        nu.Map(
            _listed(viewer, root),
            nu.Dict.of(
                id=nu.ToStr(_row.get_item(nu.Str("id"), nu.Str(""))),
                title=nu.ToStr(_row.get_item(nu.Str("name"), nu.Str(""))),
                parent=nu.Str(ROOT_ID),
                # Planes do not nest here, so the hierarchy is one level deep
                # and every Plane is a leaf of the row that stands for the
                # Space.
                children=nu.List.of(),
            ),
            key=_ROW,
        )
    )
    return nu.List.of(space) + nu.List(listed)
