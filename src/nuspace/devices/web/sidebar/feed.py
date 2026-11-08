"""The sidebar feed: one arm per interaction, all in parallel, for one tab. Host only.

Two families:

- **browser to store.** A sidebar event runs one op over its own fields.
  A failure toasts on the tab (:meth:`~nuspace.devices.web.utils.Arms.event`).
- **store to browser.** What the tree shows changed; the arm ships it again.

**A lazy tree.** The tab sees the web planes under root, and under each
branch it has open (``Conn.connections[sid].expanded``), never the whole
space. A branch is walked from its plane's ``children``, keeping the web
planes (a ``Web.planes`` row) that are not removed, in sibling order. A
plane with no web row stops the walk: what hangs under it is not listed.
A row ships its children only when its branch is open, ``[]`` otherwise,
and the walk goes down from root through shipped rows only, so a branch
left open under a closed one lists nothing until its parent opens again.
Pinned planes ship a row too, wherever they hang, so a pin always has its
title and icon.

**Rows.** A row carries its plane's name, icon, ``spec`` and ``system``
(the browser offers no delete for a plane ``plane.remove`` refuses). The
browser falls back to the registered PlaneSpec's icon when the plane has
none.

**Watches.** The tree ships again when a plane's name, icon, removal or
children change, a web row comes or goes, the pins change, or the tab
opens or closes a branch. A cell writing its state or the kernel writing a
run never wakes it. Level, with no re-checks: a missed notification leaves
the tree stale until the next change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace.devices.web import ops as web
from nuspace.devices.web.shapes import Conn, Web
from nuspace.devices.web.sidebar import interactions
from nuspace.devices.web.sidebar.interactions import KIND_PLANE, KIND_SPACE, ROOT_ID
from nuspace.devices.web.utils import Arms, field_str, placed
from nuspace.errors import Missing
from nuspace.ops.brackets import atomic
from nuspace.shapes.plane import ROOT
from nuspace.shapes.space import Space
from nuspace.specs import EMPTY_PLANE, add_plane, registered_name
from nuspace.utils import keys_of


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.specs import PlaneSpec
    from nustd.ui.core import Ref


__all__ = ["create", "node", "pins", "rows", "sidebar_feed"]


def node(parent_id: nu.Nu) -> nu.Str:
    """The store's plane for a browser parent id: :data:`ROOT_ID` is root."""
    return nu.Str(nu.Switch(parent_id, {ROOT_ID: ROOT}, default=parent_id))


def _shown(plane: nu.StrArg) -> nu.Bool:
    """Whether a plane is listed: on the web and not removed. Two reads in Space, one in Web."""
    return Web.planes.contains(plane).and_(nuspace.plane.exists(plane))


def _kids(plane: nu.StrArg) -> nu.List:
    """A branch's listed children, in sibling order: O(its children)."""
    return (
        keys_of(Space.planes[plane].children)
        .iter()
        .filter(lambda kid: _shown(nu.Str(kid)))
        .to_list()
    )


def _row(plane: nu.Str, parent: nu.StrArg, children: nu.Nu) -> nu.Dict:
    """One plane as a browser row."""
    row = Space.planes[plane]
    return nu.Dict.of(
        id=plane,
        kind=KIND_PLANE,
        title=row.name.fallback(""),
        parent=nu.If(nu.Str(parent) == ROOT, ROOT_ID, parent),
        children=children,
        spec=row.spec.fallback(""),
        icon=row.icon.fallback(""),
        system=row.system.fallback(False),
    )


class _Walk(nu.Shape):
    """A walk down the tab's open branches: the level to go down from, the rows walked."""

    level = nu.ObjectRef.slot()
    walked = nu.ObjectRef.slot()


def rows(sid: nu.StrArg, *, into: nu.Ref) -> nu.Nu:
    """The tab's tree as browser rows, set into ``into``: the space row, then the open branches.

    Walked down from root a level at a time: a branch is walked only when
    it is open and its own row was shipped, so a branch left open under a
    closed one, or under a plane off the web or removed, lists nothing.
    ``parent`` is on every row: the browser takes the first self parenting
    row as the root, so a plane row without one would become it. Bare
    term, no bracket: the caller brackets it, so the whole tree is one
    read. Cost: O(rows shipped): the children of root and of each branch
    walked, plus one level per depth walked.

    Args:
        sid: The tab.
        into: A ref set to ``[space, *planes]``, each ``{id, kind, title,
            parent, children}``, planes with ``spec``, ``icon`` and
            ``system`` too. Pinned planes not under a walked branch ship as
            rows with no children.
    """
    expanded = Conn.connections[sid].expanded
    space = nu.Dict.of(id=ROOT_ID, kind=KIND_SPACE, title="", parent=ROOT_ID, children=_kids(ROOT))
    level, walked = _Walk.level, _Walk.walked

    def with_open(held: nu.ObjectRef) -> nu.Nu:
        opened = nu.List(held)

        def under(at: nu.Attr) -> nu.List:
            """A shipped row's children as rows, with their own children when open."""
            got = nu.Dict(at)
            parent = nu.str(got["id"])

            def one(kid: nu.Attr) -> nu.Dict:
                plane = nu.Str(kid)
                return _row(plane, parent, nu.If(opened.contains(plane), _kids(plane), []))

            return nu.List(got["children"]).iter().map(one).to_list()

        down = walked.set(nu.List(walked) + nu.List(level)) >> level.set(
            nu.List(level).iter().map(under).flatten().to_list()
        )
        walk = nu.WhileDo(nu.List(level).len() > 0, down)

        def alone(at: nu.Attr) -> nu.Dict:
            plane = nu.Str(at)
            return _row(plane, Space.planes[plane].parent.fallback(ROOT), [])

        ids = nu.List(walked).iter().map(lambda r: nu.Dict(r)["id"]).to_list()
        extra = pins().iter().filter(lambda p: ids.contains(p).not_()).map(alone).to_list()
        done = into.set(nu.List(walked) + extra)
        return nu.Frame(_Walk, walk >> done, level=nu.List.of(space), walked=nu.List.create())

    return nu.let(keys_of(expanded), with_open)


def pins() -> nu.List:
    """The pinned plane ids, in order, those listed only (on the web, not removed). Bare read."""
    pinned = nu.If(Web.pinned.exists(), nu.list(Web.pinned), [])
    return nu.List(pinned).iter().filter(lambda p: _shown(nu.Str(p))).to_list()


def create(
    planes: Sequence[PlaneSpec], spec: nu.Nu, plane_id: nu.Nu, parent_id: nu.Nu, title: nu.Nu
) -> nu.Nu:
    """Make ``plane_id`` from the registered PlaneSpec ``spec`` names, ``""`` for the empty plane.

    :func:`nuspace.specs.add_plane`, a wrapper that brackets itself: the
    plane, then its state and its web row. An empty ``title`` takes the
    spec's label.

    Raises:
        Missing: No registered PlaneSpec of that name.
    """
    specs = {"": EMPTY_PLANE, **{registered_name(p): p for p in planes}}
    name = nu.Str(spec)

    def made(found: PlaneSpec) -> nu.Nu:
        called = nu.If(nu.Str(title) == "", found.label, title)
        return add_plane(found, id=plane_id, parent=node(parent_id), name=called)

    unknown = nu.Raise(nu.Str("no plane spec ") + name, exc_cls=Missing)
    return nu.SwitchDo(name, {key: made(found) for key, found in specs.items()}, default=unknown)


def _changes(sid: nu.StrArg) -> list[nu.Nu]:
    """What reships the tree: names, icons, removals and children of planes, web rows, pins, folds."""
    planes = Space.planes
    return [
        atomic(planes.on_descendants_change("*", "name")),
        atomic(planes.on_descendants_change("*", "icon")),
        atomic(planes.on_descendants_change("*", "removed_at")),
        atomic(planes.on_descendants_change("*", "children")),
        atomic(planes.on_descendants_change("*", "children", "*")),
        atomic(Web.planes.on_children_change()),
        atomic(Web.pinned.on_change()),
        atomic(Web.pinned.on_children_change()),
        atomic(Conn.connections[sid].expanded.on_change()),
    ]


def _ship(sidebar: Ref, sid: nu.StrArg) -> nu.Nu:
    """The tree and the pins read in one snapshot, then shipped."""

    def ship(tree: nu.ObjectRef, pinned: nu.ObjectRef) -> nu.Nu:
        read = atomic(rows(sid, into=tree) >> pinned.set(pins()))
        return read >> interactions.set_tree(sidebar, nu.List(tree), nu.List(pinned))

    return nu.let([], lambda tree: nu.let([], lambda pinned: ship(tree, pinned)))


def sidebar_feed(sidebar: Ref, sid: nu.StrArg, planes: Sequence[PlaneSpec], toasts: Ref) -> nu.Nu:
    """The sidebar of one tab, live, as one term. Built per tab, never ends.

    Args:
        sidebar: The shell's sidebar ref.
        sid: The tab, whose row must exist before this runs.
        planes: The registered PlaneSpecs, what ``plane.create`` can make
            beside the empty one.
        toasts: The tab's toast ref, where a failed event shows.
    """
    arms = Arms("sidebar", toasts)

    def made(plane: nu.Str, event: nu.Attr) -> nu.Nu:
        spec, parent = field_str(event, "spec"), field_str(event, "parent_id")
        return create(planes, spec, plane, parent, field_str(event, "title"))

    def moved(plane: nu.Str, event: nu.Attr) -> nu.Nu:
        under = node(field_str(event, "parent_id"))
        return placed(event, lambda **at: atomic(nuspace.plane.move(plane, parent=under, **at)))

    return nu.ParallelAsync(
        arms.states("tree", _changes(sid), _ship(sidebar, sid)),
        arms.plane_event("create", interactions.on_create_plane(sidebar), made),
        arms.plane_event(
            "rename",
            interactions.on_rename_plane(sidebar),
            lambda p, ev: atomic(nuspace.plane.rename(p, field_str(ev, "title"))),
        ),
        arms.plane_event(
            "delete",
            interactions.on_delete_plane(sidebar),
            lambda p, _: atomic(nuspace.plane.remove(p)),
        ),
        arms.plane_event("move", interactions.on_move_plane(sidebar), moved),
        arms.plane_event(
            "icon",
            interactions.on_set_icon(sidebar),
            lambda p, ev: atomic(nuspace.plane.set_icon(p, field_str(ev, "icon"))),
        ),
        arms.plane_event(
            "pin",
            interactions.on_pin_plane(sidebar),
            lambda p, ev: placed(ev, lambda **at: atomic(web.pin(p, **at))),
        ),
        arms.plane_event(
            "unpin", interactions.on_unpin_plane(sidebar), lambda p, _: atomic(web.unpin(p))
        ),
        arms.plane_event(
            "pin_move",
            interactions.on_move_pin(sidebar),
            lambda p, ev: placed(ev, lambda **at: atomic(web.move_pin(p, **at))),
        ),
        arms.plane_event(
            "expand", interactions.on_expand(sidebar), lambda p, _: atomic(web.expand(sid, p))
        ),
        arms.plane_event(
            "collapse",
            interactions.on_collapse(sidebar),
            lambda p, _: atomic(web.collapse(sid, p)),
        ),
    )
