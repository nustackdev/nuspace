"""The sidebar as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders the tree of web
planes. It holds no state and knows no store; everything it ships is
handed to it.

It is mounted with one prop off the registry: ``registered``, what the add
plane popup offers, in order. Seeded when the shell boots, like the viewer's
``/`` menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.devices.web.sidebar import interactions
from nuspace.devices.web.utils import SpaceRef
from nuspace.specs import registered_name


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nu.lang import ListArg, Nu
    from nuspace.specs import PlaneSpec
    from nustd.ui.core import Changed


__all__ = ["SidebarRef", "registered_entries"]


def registered_entries(planes: Iterable[PlaneSpec]) -> list[dict]:
    """The popup's entries, ``{name, label, group, icon, description}`` in registry order."""
    return [
        {
            "name": registered_name(p),
            "label": p.label,
            "group": p.group,
            "icon": p.icon,
            "description": p.description,
        }
        for p in planes
    ]


class SidebarRef(SpaceRef):
    """The web planes, as one browser node."""

    _wire_type: ClassVar[str] = "SidebarRef"

    @classmethod
    def slot(cls, *, registered: Sequence[Mapping[str, object]] | None = None) -> Self:
        """Mount the sidebar, seeded with the registered Planes."""
        return super().slot(registered=[dict(r) for r in registered or ()])

    def set_tree(self, rows: ListArg[dict]) -> Nu:
        """Replace the tree."""
        return interactions.set_tree(self, rows)

    def on_create_plane(self) -> Changed:
        """``{plane_id, parent_id, spec, title}``."""
        return interactions.on_create_plane(self)

    def on_rename_plane(self) -> Changed:
        """``{plane_id, title}``."""
        return interactions.on_rename_plane(self)

    def on_delete_plane(self) -> Changed:
        """``{plane_id}``."""
        return interactions.on_delete_plane(self)

    def on_move_plane(self) -> Changed:
        """``{plane_id, parent_id, before?, after?}``."""
        return interactions.on_move_plane(self)

    def on_expand(self) -> Changed:
        """``{plane_id}``."""
        return interactions.on_expand(self)

    def on_collapse(self) -> Changed:
        """``{plane_id}``."""
        return interactions.on_collapse(self)
