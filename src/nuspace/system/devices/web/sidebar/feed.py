"""The sidebar feed: one arm per interaction, all in parallel. Host only.

Two families:

- **browser to store.** A sidebar event runs one op over its own fields.
- **store to browser.** The tree changed; the arm ships it again.

**One tree.** Every plane with ``props.ui`` is listed, under its parent in
``Space.tree`` and in that node's sibling order, top level planes under the
space row. ``made_by`` and ``system`` group nothing. A drawn plane whose
parent is not drawn (a service's child, or one no node lists) is shown at the
top level, after the rest, so nothing drawn goes missing.

**Icons.** A row carries its plane's ``meta.icon`` and no other meta key.
The browser falls back to the registered Plane's icon when it is empty.

**Narrow watch.** The tree is shipped again when the set of planes, a
plane's name, props or icon, or a tree node change, and nothing else: a
cell writing its state or the kernel writing a run never wakes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import flag, fresh
from nuspace.shapes import ROOT, Space
from nuspace.system.devices.web.sidebar import interactions
from nuspace.system.devices.web.sidebar.interactions import KIND_PLANE, KIND_SPACE, ROOT_ID
from nuspace.system.devices.web.utils import Arms, field_str
from nuspace.system.kernel.utils import snap


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.ops import Plane
    from nustd.ui.core import Ref


__all__ = ["create", "move", "node", "rows", "sidebar_feed"]


_arms = Arms("sidebar")

# The event attrs, one per arm: parallel arms share one ``ctx.attrs``.
_CREATE = "nuspace.web.sidebar.create"
_RENAME = "nuspace.web.sidebar.rename"
_DELETE = "nuspace.web.sidebar.delete"
_MOVE = "nuspace.web.sidebar.move"
_ICON = "nuspace.web.sidebar.icon"


def _text(row: nu.Nu, field: str) -> nu.Nu:
    return nu.ToStr(row.get_item(nu.Str(field), nu.Str("")))


def _prop(row: nu.Nu, field: str) -> nu.Nu:
    """One of a plane row's props. The row carries them whole, defaults filled in."""
    return nu.Dict(row.get_item(nu.Str("props"), nu.Dict.of())).get_item(nu.Str(field))


def _icon(row: nu.Nu) -> nu.Nu:
    """A plane row's ``meta.icon``, ``""`` when it has none."""
    meta = nu.Dict(row.get_item(nu.Str("meta"), nu.Dict.of()))
    return nu.ToStr(meta.get_item(nu.Str("icon"), nu.Str("")))


def node(parent_id: nu.Nu) -> nu.Nu:
    """The store's tree node for a browser parent id: :data:`ROOT_ID` and ``""`` are ``ROOT``."""
    top = nu.Or(nu.Eq(parent_id, nu.Str(ROOT_ID)), nu.Eq(parent_id, nu.Str("")))
    return nu.If(top, nu.Str(ROOT), parent_id)


def _drawn(plane_id: nu.Nu) -> nu.Nu:
    return flag(Space.planes[plane_id].props.ui, False)


def rows() -> nu.Nu:
    """The space and every drawn plane, as browser rows. Bare read.

    ``parent`` is on every row: the browser defaults it to the row's own id
    and takes the first self parenting row as the root, so a plane row
    without one would become the root.

    Yields:
        ``[space, *planes]``, each ``{id, kind, title, parent, children}``,
        planes with ``made_by`` and ``icon`` too. Planes in creation order, ``children``
        in sibling order.
    """
    pick, each, kid = fresh("sidebar_pick"), fresh("sidebar_row"), fresh("sidebar_kid")
    listed, known = fresh("sidebar_listed"), fresh("sidebar_known")
    picked, row = nu.DictAttrRef(pick), nu.DictAttrRef(each)
    held, ids = nu.ListAttrRef(listed), nu.ListAttrRef(known)
    shown = nu.List(
        nu.Collect(nu.Filter(ops.plane_rows(), nu.ToBool(_prop(picked, "ui")), key=pick))
    )

    def kids(node_id: nu.Nu) -> nu.Nu:
        return nu.List(
            nu.Collect(nu.Filter(ops.children(node_id), ids.contains(nu.AnyAttrRef(kid)), key=kid))
        )

    def listed_under(row: nu.Nu) -> nu.Nu:
        """Whether the row's parent is drawn too, so the row hangs under it."""
        return ids.contains(_text(row, "parent"))

    # Drawn planes whose parent is neither drawn nor the root: shown at the top.
    stray = nu.Filter(
        held,
        nu.And(nu.Ne(_text(picked, "parent"), nu.Str(ROOT)), nu.Not(listed_under(picked))),
        key=pick,
    )
    space = nu.Dict.of(
        id=nu.Str(ROOT_ID),
        kind=nu.Str(KIND_SPACE),
        # Empty: the browser draws its own word for the space here.
        title=nu.Str(""),
        parent=nu.Str(ROOT_ID),
        children=kids(nu.Str(ROOT))
        + nu.List(nu.Collect(nu.Map(stray, _text(row, "id"), key=each))),
    )
    planes = nu.List(
        nu.Collect(
            nu.Map(
                held,
                nu.Dict.of(
                    id=_text(row, "id"),
                    kind=nu.Str(KIND_PLANE),
                    title=_text(row, "name"),
                    parent=nu.If(listed_under(row), _text(row, "parent"), nu.Str(ROOT_ID)),
                    children=kids(_text(row, "id")),
                    made_by=nu.ToStr(_prop(row, "made_by")),
                    icon=_icon(row),
                ),
                key=each,
            )
        )
    )
    body = nu.Let(
        known,
        nu.List(nu.Collect(nu.Map(held, _text(picked, "id"), key=pick))),
        nu.List.of(space) + planes,
    )
    return nu.Let(listed, shown, body)


def create(
    planes: Sequence[Plane], made_by: nu.Nu, plane_id: nu.Nu, parent_id: nu.Nu, title: nu.Nu
) -> nu.Nu | None:
    """Create ``plane_id`` from the registered Plane ``made_by`` names.

    A name nothing registered answers to creates the first Plane. An empty
    ``title`` takes the Plane's label. None when nothing is registered.
    """
    if not planes:
        return None
    named = [nu.Eq(made_by, nu.Str(spec.name)) for spec in planes]
    unknown = nu.Not(named[0] if len(named) == 1 else nu.Or(*named))
    branches = [
        nu.IfDo(
            nu.Or(named[0], unknown) if i == 0 else named[i],
            ops.create_plane(
                spec,
                parent=node(parent_id),
                name=nu.If(nu.Eq(title, nu.Str("")), nu.Str(spec.label), title),
                plane_id=plane_id,
            ),
        )
        for i, spec in enumerate(planes)
    ]
    return branches[0] if len(branches) == 1 else nu.Sequential(*branches)


def move(plane_id: nu.Nu, parent_id: nu.Nu, index: nu.Nu) -> nu.Nu:
    """Move a plane to ``index`` among the drawn children of ``parent_id``.

    The browser counts only what it draws, the store's node holds planes it
    does not (services, for one). The position goes in before the drawn
    sibling the browser named, or at the end when it named none.
    """
    under, others, drawn = fresh("sidebar_under"), fresh("sidebar_others"), fresh("sidebar_drawn")
    at = fresh("sidebar_at")
    item = nu.AnyAttrRef(at)
    everyone = nu.List(
        nu.Collect(nu.Filter(ops.children(nu.StrAttrRef(under)), nu.Ne(item, plane_id), key=at))
    )
    shown = nu.List(nu.Collect(nu.Filter(nu.ListAttrRef(others), _drawn(nu.ToStr(item)), key=at)))
    rest, seen = nu.ListAttrRef(others), nu.ListAttrRef(drawn)
    position = nu.If(
        nu.And(nu.Ge(index, nu.Int(0)), nu.Lt(index, seen.len())),
        rest.index(seen[index]),
        rest.len(),
    )
    return nu.Let(
        under,
        node(parent_id),
        nu.Let(
            others,
            snap(everyone),
            nu.Let(
                drawn,
                snap(shown),
                ops.move_plane(plane_id, parent=nu.StrAttrRef(under), index=position),
            ),
        ),
    )


def _changes() -> list[nu.Nu]:
    """What reships the tree: the set of planes, their names, props and icons, the tree nodes."""
    planes, tree = Space.planes, Space.tree
    return [
        snap(planes.on_children_change()),
        snap(planes.on_descendants_change("*", "name")),
        snap(planes.on_descendants_change("*", "props")),
        snap(planes.on_descendants_change("*", "props", "*")),
        snap(planes.on_descendants_change("*", "meta")),
        snap(planes.on_descendants_change("*", "meta", "icon")),
        snap(tree.on_children_change()),
        snap(tree.on_descendants_change("*", "children")),
        snap(tree.on_descendants_change("*", "children", "*")),
    ]


def _ship(sidebar: Ref) -> nu.Nu:
    held = fresh("sidebar_ship")
    return nu.Let(held, snap(rows()), interactions.set_tree(sidebar, nu.ListAttrRef(held)))


def sidebar_feed(sidebar: Ref, planes: Sequence[Plane]) -> nu.Nu:
    """The sidebar, live, as one term. Built per connection, never ends.

    Args:
        sidebar: The shell's sidebar ref.
        planes: The registered Planes, what ``plane.create`` can create.
    """
    arms = [_arms.state("tree", _changes(), _ship(sidebar))]
    plane_id = field_str(_CREATE, "plane_id")
    made = create(
        planes,
        field_str(_CREATE, "made_by"),
        plane_id,
        field_str(_CREATE, "parent_id"),
        field_str(_CREATE, "title"),
    )
    if made is not None:
        arms.append(
            _arms.event(
                _CREATE,
                interactions.on_create_plane(sidebar),
                nu.IfDo(nu.Ne(plane_id, nu.Str("")), made),
            )
        )
    renamed = field_str(_RENAME, "plane_id")
    deleted = field_str(_DELETE, "plane_id")
    moved = field_str(_MOVE, "plane_id")
    iconed = field_str(_ICON, "plane_id")
    arms += [
        _arms.event(
            _RENAME,
            interactions.on_rename_plane(sidebar),
            nu.IfDo(
                nu.Ne(renamed, nu.Str("")),
                ops.rename_plane(renamed, field_str(_RENAME, "title")),
            ),
        ),
        _arms.event(
            _DELETE,
            interactions.on_delete_plane(sidebar),
            nu.IfDo(nu.Ne(deleted, nu.Str("")), ops.remove_plane(deleted)),
        ),
        _arms.event(
            _MOVE,
            interactions.on_move_plane(sidebar),
            nu.IfDo(
                nu.Ne(moved, nu.Str("")),
                move(
                    moved,
                    field_str(_MOVE, "parent_id"),
                    nu.ToInt(nu.DictAttrRef(_MOVE).get_item(nu.Str("index"), nu.Int(-1))),
                ),
            ),
        ),
        _arms.event(
            _ICON,
            interactions.on_set_icon(sidebar),
            nu.IfDo(
                nu.Ne(iconed, nu.Str("")),
                ops.set_plane_icon(iconed, field_str(_ICON, "icon")),
            ),
        ),
    ]
    return nu.ParallelAsync(*arms)
