"""The viewer as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders the open planes'
cells, one pane per plane.
It never asks what kind of plane it draws; what it reads off the plane is
its web flags (``editable``, ``full_width``, ``compact``), which arrive with
the plane like anything else, and go back through ``plane.web``.

It is mounted with one prop off the registered Cells (D19):
``cell_specs``, the ``/`` menu's entries in order, each with its classes and
the classes it is the default of, which is how the input line finds what
typing creates. Seeded when the shell boots,
since the Cells are the host's registry and the shell is a static class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.devices.web.utils import SpaceRef
from nuspace.devices.web.viewer import interactions
from nuspace.specs import registered_name


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nu.lang import DictArg, ListArg, Nu, StrArg
    from nuspace.specs import CellSpec
    from nustd.ui.core import Changed


__all__ = ["ViewerRef", "slash_entries"]


def slash_entries(cells: Iterable[CellSpec]) -> list[dict]:
    """The ``/`` menu's entries, ``{name, label, group, icon, description, classes, default_for}`` in registry order.

    ``classes`` are the spec's own. ``default_for`` is resolved here, so the
    browser finds a class's default by looking, never by choosing: a class
    two specs claim is listed only under the first in registry order.
    """
    claimed: set[str] = set()
    entries = []
    for s in cells:
        default_for = [c for c in s.default_for if c not in claimed]
        claimed.update(default_for)
        entries.append(
            {
                "name": registered_name(s),
                "label": s.label,
                "group": s.group,
                "icon": s.icon,
                "description": s.description,
                "classes": list(s.classes),
                "default_for": default_for,
            }
        )
    return entries


class ViewerRef(SpaceRef):
    """The open planes' cells, as one browser node."""

    _wire_type: ClassVar[str] = "ViewerRef"

    @classmethod
    def slot(cls, *, cell_specs: Sequence[Mapping[str, object]] | None = None) -> Self:
        """Mount the viewer, seeded with the ``/`` menu."""
        return super().slot(cell_specs=[dict(s) for s in cell_specs or ()])

    def set_plane(
        self,
        plane_id: StrArg,
        *,
        title: StrArg,
        meta: DictArg[str, object],
        cells: ListArg[dict],
    ) -> Nu:
        """Replace what one pane draws: one plane, its meta, and its cells in order."""
        return interactions.set_plane(self, plane_id, title=title, meta=meta, cells=cells)

    def set_absent(self, plane_id: StrArg, reason: StrArg) -> Nu:
        """Say one pane has nothing to draw: its plane is missing or headless."""
        return interactions.set_absent(self, plane_id, reason)

    def set_status(self, plane_id: StrArg, statuses: ListArg[dict]) -> Nu:
        """Patch what one pane says about its cells."""
        return interactions.set_status(self, plane_id, statuses)

    def on_open(self) -> Changed:
        """``{plane_ids}``, the full ordered list."""
        return interactions.on_open(self)

    def on_create_cell(self) -> Changed:
        """``{plane_id, cell_id, name, before?, after?}``."""
        return interactions.on_create_cell(self)

    def on_update_cell(self) -> Changed:
        """``{cell_id, source}``."""
        return interactions.on_update_cell(self)

    def on_delete_cell(self) -> Changed:
        """``{cell_id}``."""
        return interactions.on_delete_cell(self)

    def on_move_cell(self) -> Changed:
        """``{cell_id, before?, after?}``."""
        return interactions.on_move_cell(self)

    def on_restart_cell(self) -> Changed:
        """``{cell_id}``."""
        return interactions.on_restart_cell(self)

    def on_restart_plane(self) -> Changed:
        """``{plane_id}``."""
        return interactions.on_restart_plane(self)

    def on_set_web(self) -> Changed:
        """``{plane_id, flags}``."""
        return interactions.on_set_web(self)
