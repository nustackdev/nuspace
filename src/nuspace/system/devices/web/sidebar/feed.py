"""The sidebar feed: one arm per interaction, all in parallel. Host only.

Two families:

- **browser to store.** A sidebar event runs one op over its own fields.
- **store to browser.** The plane list changed; the arm ships it again.

**Sections are apps** (D18). One section row per app with ``section=True``,
in the order the apps were given. A plane is listed when its ``props.ui``
is set and its ``props.made_by`` names a section app; it hangs under that
section. ``+`` under a section runs its app. ``system`` is not asked, it
only means protected: home is a system ui plane with ``made_by`` empty, so
it is under no section, and the space header is its way in.

**Narrow watch.** The list is shipped again when the set of planes, a
plane's name or props change, and nothing else: a cell writing
its state or the kernel writing a run never wakes it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.ops.utils import fresh
from nuspace.shapes import Space
from nuspace.system.devices.web.sidebar import interactions
from nuspace.system.devices.web.sidebar.interactions import (
    KIND_GROUP,
    KIND_PLANE,
    KIND_SPACE,
    ROOT_ID,
)
from nuspace.system.devices.web.utils import Arms, field_str
from nuspace.system.kernel.utils import snap


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.ops import App
    from nustd.ui.core import Ref


__all__ = ["create_plane", "rows", "sections", "sidebar_feed"]


_arms = Arms("sidebar")

# The event attrs, one per arm: parallel arms share one ``ctx.attrs``.
_CREATE = "nuspace.web.sidebar.create"
_RENAME = "nuspace.web.sidebar.rename"
_DELETE = "nuspace.web.sidebar.delete"


def sections(apps: Sequence[App]) -> list[App]:
    """The apps that declare a sidebar section, in order."""
    return [app for app in apps if app.section]


def _any(conds: list[nu.Nu]) -> nu.Nu:
    return conds[0] if len(conds) == 1 else nu.Or(*conds)


def _text(row: nu.Nu, field: str) -> nu.Nu:
    return nu.ToStr(row.get_item(nu.Str(field), nu.Str("")))


def _prop(row: nu.Nu, field: str) -> nu.Nu:
    """One of a plane row's props. The row carries them whole, defaults filled in."""
    return nu.Dict(row.get_item(nu.Str("props"), nu.Dict.of())).get_item(nu.Str(field))


def rows(apps: Sequence[App]) -> nu.Nu:
    """The space, its sections and every listed plane, as browser rows. Bare read.

    ``parent`` is on every row: the browser defaults it to the row's own id
    and takes the first self parenting row as the root, so a plane row
    without one would become the root.

    Yields:
        ``[space, *sections, *planes]``, each ``{id, kind, title, parent,
        children}``. Planes in creation order.
    """
    groups = sections(apps)
    names = nu.List.of(*[nu.Str(app.name) for app in groups])
    pick, each, listed = fresh("sidebar_pick"), fresh("sidebar_row"), fresh("sidebar_listed")
    picked = nu.DictAttrRef(pick)
    row = nu.DictAttrRef(each)
    shown = nu.List(
        nu.Collect(
            nu.Filter(
                ops.plane_rows(),
                nu.And(
                    nu.ToBool(_prop(picked, "ui")),
                    names.contains(nu.ToStr(_prop(picked, "made_by"))),
                ),
                key=pick,
            )
        )
    )
    held = nu.ListAttrRef(listed)

    def ids(group: str) -> nu.Nu:
        return nu.List(
            nu.Collect(
                nu.Map(
                    nu.Filter(held, nu.Eq(nu.ToStr(_prop(picked, "made_by")), group), key=pick),
                    _text(row, "id"),
                    key=each,
                )
            )
        )

    space = nu.Dict.of(
        id=nu.Str(ROOT_ID),
        kind=nu.Str(KIND_SPACE),
        # Empty: the browser draws its own word for the space here.
        title=nu.Str(""),
        parent=nu.Str(ROOT_ID),
        children=nu.List.of(*[nu.Str(app.name) for app in groups]),
    )
    grouped = [
        nu.Dict.of(
            id=nu.Str(app.name),
            kind=nu.Str(KIND_GROUP),
            title=nu.Str(app.label),
            parent=nu.Str(ROOT_ID),
            children=ids(app.name),
        )
        for app in groups
    ]
    planes = nu.List(
        nu.Collect(
            nu.Map(
                held,
                nu.Dict.of(
                    id=_text(row, "id"),
                    kind=nu.Str(KIND_PLANE),
                    title=_text(row, "name"),
                    parent=nu.ToStr(_prop(row, "made_by")),
                    # Nesting is not drawn yet: every plane is a leaf of its section.
                    children=nu.List.of(),
                ),
                key=each,
            )
        )
    )
    return nu.Let(listed, shown, nu.List.of(space, *grouped) + planes)


def create_plane(
    apps: Sequence[App], group: nu.StrArg, plane_id: nu.StrArg, name: nu.StrArg
) -> nu.Nu | None:
    """Run the section app ``group`` names, making ``plane_id`` called ``name``.

    A group no section app answers to runs the first one. None when there is
    no section app at all.
    """
    groups = sections(apps)
    if not groups:
        return None
    named = [nu.Eq(group, nu.Str(app.name)) for app in groups]
    branches = [
        nu.IfDo(
            nu.Or(named[0], nu.Not(_any(named))) if i == 0 else named[i],
            ops.run_app(app, plane_id=plane_id, name=name),
        )
        for i, app in enumerate(groups)
    ]
    return branches[0] if len(branches) == 1 else nu.Sequential(*branches)


def _changes() -> list[nu.Nu]:
    """What reships the list: the set of planes, their names and props."""
    planes = Space.planes
    return [
        snap(planes.on_children_change()),
        snap(planes.on_descendants_change("*", "name")),
        snap(planes.on_descendants_change("*", "props")),
        snap(planes.on_descendants_change("*", "props", "*")),
    ]


def _ship(sidebar: Ref, apps: Sequence[App]) -> nu.Nu:
    held = fresh("sidebar_ship")
    return nu.Let(held, snap(rows(apps)), interactions.set_tree(sidebar, nu.ListAttrRef(held)))


def sidebar_feed(sidebar: Ref, apps: Sequence[App]) -> nu.Nu:
    """The sidebar, live, as one term. Built per connection, never ends.

    Args:
        sidebar: the shell's sidebar ref.
        apps: the registered apps. Those with ``section=True`` are sections.
    """
    arms = [_arms.state("tree", _changes(), _ship(sidebar, apps))]
    page_id = field_str(_CREATE, "page_id")
    create = create_plane(apps, field_str(_CREATE, "group"), page_id, field_str(_CREATE, "title"))
    if create is not None:
        arms.append(
            _arms.event(
                _CREATE,
                interactions.on_create_plane(sidebar),
                nu.IfDo(nu.Ne(page_id, nu.Str("")), create),
            )
        )
    renamed = field_str(_RENAME, "page_id")
    deleted = field_str(_DELETE, "page_id")
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
    ]
    return nu.ParallelAsync(*arms)
