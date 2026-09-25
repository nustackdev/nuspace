"""The sidebar as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders the tree of planes
that draw. It holds no state and knows no store; everything it ships is
handed to it.

It is mounted with one prop off the registered Planes: ``registered``, what
the add plane popup offers, in order. Seeded when the shell boots, like the
viewer's ``/`` menu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.system.devices.web.sidebar import interactions
from nuspace.system.devices.web.utils import SpaceRef


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nu.lang import ListArg, Nu
    from nuspace.ops import Plane
    from nustd.ui.core import Changed


__all__ = ["SidebarRef", "registered_entries"]


def registered_entries(planes: Iterable[Plane]) -> list[dict]:
    """The popup's entries, ``{name, label, icon, description}`` in registry order."""
    return [
        {"name": p.name, "label": p.label, "icon": p.icon, "description": p.description}
        for p in planes
    ]


class SidebarRef(SpaceRef):
    """Every plane that draws, as one browser node."""

    _wire_type: ClassVar[str] = "SidebarRef"

    @classmethod
    def slot(cls, *, registered: Sequence[Mapping[str, object]] | None = None) -> Self:
        """Mount the sidebar, seeded with the registered Planes."""
        return super().slot(registered=[dict(r) for r in registered or ()])

    def set_tree(self, rows: ListArg[dict], pinned: ListArg[str]) -> Nu:
        """Replace the tree and the pins."""
        return interactions.set_tree(self, rows, pinned)

    def on_create_plane(self) -> Changed:
        """``{plane_id, parent_id, made_by, title}``."""
        return interactions.on_create_plane(self)

    def on_rename_plane(self) -> Changed:
        """``{plane_id, title}``."""
        return interactions.on_rename_plane(self)

    def on_delete_plane(self) -> Changed:
        """``{plane_id}``."""
        return interactions.on_delete_plane(self)

    def on_move_plane(self) -> Changed:
        """``{plane_id, parent_id, index}``."""
        return interactions.on_move_plane(self)

    def on_pin_plane(self) -> Changed:
        """``{plane_id, index}``."""
        return interactions.on_pin_plane(self)

    def on_unpin_plane(self) -> Changed:
        """``{plane_id}``."""
        return interactions.on_unpin_plane(self)

    def on_move_pin(self) -> Changed:
        """``{plane_id, index}``."""
        return interactions.on_move_pin(self)
