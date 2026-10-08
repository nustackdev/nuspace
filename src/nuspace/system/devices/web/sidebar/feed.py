"""The sidebar feed: one arm per interaction, all in parallel. Host only.

Two families:

- **browser to store.** A sidebar event runs one op over its own fields.
- **store to browser.** The tree changed; the arm ships it again.

**One tree.** Every plane with ``props.ui`` is listed, under its parent and
in its parent's sibling order, top level planes (``Space.top``) under the
space row. ``made_by`` and ``system`` group nothing. A drawn plane whose
parent is not drawn (a service's child) is shown at the top level, after the
rest, so nothing drawn goes missing.

**Icons.** A row carries its plane's ``meta.icon`` and no other meta key.
The browser falls back to the registered Plane's icon when it is empty.

**System.** A row carries ``props.system``, so the browser offers no delete
for a plane ``remove_plane`` refuses.

**Pins.** ``Space.pinned`` ships with the tree, in order, drawn planes only.
A pin is a shortcut: the pinned plane is in the tree as well.

**Search.** ``search.run`` makes a search (:func:`~nuspace.system.search.search`)
over the snippets the space registered with a ``search``; the browser opens
the search plane itself.

**Narrow watch.** The tree is shipped again when the set of planes, a
plane's name, props or icon, the nesting, or the pins change, and nothing
else: a cell writing its state or the kernel writing a run never wakes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import field_str
from nuspace.shapes import Space
from nuspace.system import search
from nuspace.system.devices.web.sidebar import interactions
from nuspace.system.devices.web.sidebar.interactions import KIND_PLANE, KIND_SPACE, ROOT_ID
from nuspace.system.devices.web.utils import Arms, field_ids, field_index
from nuspace.system.kernel.utils import snap


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.ops import Plane, Snippet
    from nustd.ui.core import Ref


__all__ = ["create", "move", "node", "pins", "rows", "searched", "sidebar_feed"]


_arms = Arms("sidebar")


def _prop(row: nu.Nu, field: str) -> nu.Object:
    """One of a plane row's props. The row carries them whole, defaults filled in."""
    return nu.Dict(nu.Dict(row).get_item("props", nu.Dict.of())).get_item(field)


def node(parent_id: nu.Nu) -> nu.Str:
    """The store's parent for a browser parent id: :data:`ROOT_ID` is the top level, ``""``."""
    return nu.Str(nu.Switch(parent_id, {ROOT_ID: ""}, default=parent_id))


class _Listing(nu.Shape):
    """What :func:`rows` reads once: the drawn plane rows, and their ids."""

    rows = nu.ObjectRef.slot()
    ids = nu.ObjectRef.slot()


class _Moving(nu.Shape):
    """What :func:`move` reads before it moves: the parent, its other children, those drawn."""

    under = nu.StrRef.slot()
    others = nu.ObjectRef.slot()
    drawn = nu.ObjectRef.slot()


def rows() -> nu.Nu:
    """The space and every drawn plane, as browser rows. Bare read.

    ``parent`` is on every row: the browser defaults it to the row's own id
    and takes the first self parenting row as the root, so a plane row
    without one would become the root.

    Yields:
        ``[space, *planes]``, each ``{id, kind, title, parent, children}``,
        planes with ``made_by``, ``icon`` and ``system`` too. Planes in
        creation order, ``children`` in sibling order.
    """
    held, ids = _Listing.rows, _Listing.ids

    def kids(plane_id: nu.StrArg) -> nu.List:
        return ops.children(plane_id).iter().filter(lambda kid: ids.contains(kid)).to_list()

    def listed_under(row: nu.Nu) -> nu.Bool:
        """Whether the row's parent is drawn too, so the row hangs under it."""
        return ids.contains(field_str(row, "parent"))

    def plane(row: nu.Attr) -> nu.Dict:
        return nu.Dict.of(
            id=field_str(row, "id"),
            kind=KIND_PLANE,
            title=field_str(row, "name"),
            parent=nu.If(listed_under(row), field_str(row, "parent"), ROOT_ID),
            children=kids(field_str(row, "id")),
            made_by=nu.str(_prop(row, "made_by")),
            icon=field_str(nu.Dict(row).get_item("meta", nu.Dict.of()), "icon"),
            system=nu.bool(_prop(row, "system")),
        )

    # Drawn planes whose parent is neither drawn nor the top: shown at the top.
    stray = nu.Filter(
        held,
        lambda row: (field_str(row, "parent") != "").and_(listed_under(row).not_()),
    )
    space = nu.Dict.of(
        id=ROOT_ID,
        kind=KIND_SPACE,
        # Empty: the browser draws its own word for the space here.
        title="",
        parent=ROOT_ID,
        children=kids("") + nu.List(nu.Collect(nu.Map(stray, lambda row: field_str(row, "id")))),
    )
    return nu.Frame(
        _Listing,
        nu.List.of(space) + nu.List(nu.Collect(nu.Map(held, plane))),
        rows=ops.plane_rows().iter().filter(lambda row: nu.bool(_prop(row, "ui"))).to_list(),
        ids=nu.List(nu.Collect(nu.Map(held, lambda row: field_str(row, "id")))),
    )


def pins() -> nu.List:
    """The pinned plane ids, in order, those that draw only. Bare read."""
    pinned = ops.pinned().iter()
    return pinned.filter(lambda p: Space.planes[nu.Str(p)].props.ui.fallback(False)).to_list()


def create(
    planes: Sequence[Plane], made_by: nu.Nu, plane_id: nu.Nu, parent_id: nu.Nu, title: nu.Nu
) -> nu.Nu | None:
    """Create ``plane_id`` from the registered Plane ``made_by`` names.

    A name nothing registered answers to creates the first Plane. An empty
    ``title`` takes the Plane's label. None when nothing is registered.
    """
    if not planes:
        return None
    named = [nu.Str(made_by) == spec.name for spec in planes]
    unknown = nu.Not(nu.Or(*named))
    return nu.Sequential(
        *(
            nu.IfDo(
                named[0].or_(unknown) if i == 0 else named[i],
                ops.create_plane(
                    spec,
                    parent=node(parent_id),
                    name=nu.If(nu.Str(title) == "", spec.label, title),
                    plane_id=plane_id,
                ),
            )
            for i, spec in enumerate(planes)
        )
    )


def move(plane_id: nu.Nu, parent_id: nu.Nu, index: nu.Nu) -> nu.Nu:
    """Move a plane to ``index`` among the drawn children of ``parent_id``.

    The browser counts only what it draws, the store's parent lists planes it
    does not (services, for one). The position goes in before the drawn
    sibling the browser named, or at the end when it named none.
    """
    under, rest, seen = _Moving.under, nu.List(_Moving.others), nu.List(_Moving.drawn)
    i = nu.Int(index)
    position = nu.If((i >= 0).and_(i < seen.len()), rest.index(seen[i]), rest.len())
    others = ops.children(under).iter().filter(lambda p: p != plane_id)
    drawn = rest.iter().filter(lambda p: Space.planes[nu.Str(p)].props.ui.fallback(False))
    return nu.Frame(
        _Moving,
        ops.move_plane(plane_id, parent=under, index=position),
        under=node(parent_id),
        others=snap(others.to_list()),
        drawn=snap(drawn.to_list()),
    )


def _changes() -> list[nu.Nu]:
    """What reships the tree: the planes, their names, props and icons, the nesting, the pins."""
    planes = Space.planes
    return [
        snap(planes.on_children_change()),
        snap(planes.on_descendants_change("*", "name")),
        snap(planes.on_descendants_change("*", "props")),
        snap(planes.on_descendants_change("*", "props", "*")),
        snap(planes.on_descendants_change("*", "meta")),
        snap(planes.on_descendants_change("*", "meta", "icon")),
        snap(planes.on_descendants_change("*", "children")),
        snap(planes.on_descendants_change("*", "children", "*")),
        snap(Space.top.on_change()),
        snap(Space.top.on_children_change()),
        snap(Space.pinned.on_change()),
        snap(Space.pinned.on_children_change()),
    ]


def _ship(sidebar: Ref) -> nu.Nu:
    def ship(held: nu.ObjectRef) -> nu.Nu:
        return nu.let(snap(pins()), lambda pinned: interactions.set_tree(sidebar, held, pinned))

    return nu.let(snap(rows()), ship)


def searched(snippets: Sequence[Snippet], event: nu.Nu) -> nu.Nu:
    """``search.run``'s op: a search over what ``event`` names, when the query is not blank."""
    query = field_str(event, "query")
    made = search.search(
        query,
        field_ids(event, "snippets"),
        nu.bool(nu.Dict(event).get_item("titles", True)),
        searchers=search.searchable(snippets),
    )
    return nu.IfDo(query.strip() != "", made)


def sidebar_feed(sidebar: Ref, planes: Sequence[Plane], snippets: Sequence[Snippet] = ()) -> nu.Nu:
    """The sidebar, live, as one term. Built per connection, never ends.

    Args:
        sidebar: The shell's sidebar ref.
        planes: The registered Planes, what ``plane.create`` can create.
        snippets: The registered snippets, what ``search.run`` can search.
    """
    arms = [_arms.states("tree", _changes(), _ship(sidebar))]
    if planes:

        def made(plane_id: nu.Str, event: nu.Attr) -> nu.Nu:
            made_by, parent_id = field_str(event, "made_by"), field_str(event, "parent_id")
            return create(planes, made_by, plane_id, parent_id, field_str(event, "title"))

        arms.append(_arms.plane_event("create", interactions.on_create_plane(sidebar), made))
    return nu.ParallelAsync(
        *arms,
        _arms.plane_event(
            "rename",
            interactions.on_rename_plane(sidebar),
            lambda p, event: ops.rename_plane(p, field_str(event, "title")),
        ),
        _arms.plane_event(
            "delete", interactions.on_delete_plane(sidebar), lambda p, _: ops.remove_plane(p)
        ),
        _arms.plane_event(
            "move",
            interactions.on_move_plane(sidebar),
            lambda p, event: move(
                p, field_str(event, "parent_id"), field_index(event, "index", -1)
            ),
        ),
        _arms.plane_event(
            "icon",
            interactions.on_set_icon(sidebar),
            lambda p, event: ops.set_plane_icon(p, field_str(event, "icon")),
        ),
        _arms.plane_event(
            "pin",
            interactions.on_pin_plane(sidebar),
            lambda p, event: ops.pin_plane(p, field_index(event, "index", -1)),
        ),
        _arms.plane_event(
            "unpin", interactions.on_unpin_plane(sidebar), lambda p, _: ops.unpin_plane(p)
        ),
        _arms.plane_event(
            "pin_move",
            interactions.on_move_pin(sidebar),
            lambda p, event: ops.move_pin(p, field_index(event, "index", -1)),
        ),
        _arms.event("search", interactions.on_search(sidebar), lambda e: searched(snippets, e)),
    )
