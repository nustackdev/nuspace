"""The viewer as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders the open planes'
cells, one pane per plane.
It never asks what kind of plane it draws; what it reads off the plane is
its meta (``editable``, ``full_width``), which arrives with the plane like
anything else, and goes back through ``plane.meta``.

It is mounted with one prop off the registered snippets (D19):
``snippets``, the ``/`` menu's entries in order. Seeded when the shell boots,
since the snippets are the host's registry and the shell is a static class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.system.devices.web.utils import SpaceRef
from nuspace.system.devices.web.viewer import interactions


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nu.lang import DictArg, ListArg, Nu, StrArg
    from nuspace.ops import Snippet
    from nustd.ui.core import Changed


__all__ = ["ViewerRef", "slash_entries"]


def slash_entries(snippets: Iterable[Snippet]) -> list[dict]:
    """The ``/`` menu's entries, ``{name, label}`` in registry order."""
    return [{"name": s.name, "label": s.label} for s in snippets]


class ViewerRef(SpaceRef):
    """The open planes' cells, as one browser node."""

    _wire_type: ClassVar[str] = "ViewerRef"

    @classmethod
    def slot(cls, *, snippets: Sequence[Mapping[str, object]] | None = None) -> Self:
        """Mount the viewer, seeded with the ``/`` menu."""
        return super().slot(snippets=[dict(s) for s in snippets or ()])

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

    def set_status(self, plane_id: StrArg, statuses: ListArg[dict]) -> Nu:
        """Patch what one pane says about its cells."""
        return interactions.set_status(self, plane_id, statuses)

    def on_open(self) -> Changed:
        """``{plane_ids}``, the full ordered list."""
        return interactions.on_open(self)

    def on_create_cell(self) -> Changed:
        """``{plane_id, cell_id, name, index}``."""
        return interactions.on_create_cell(self)

    def on_update_cell(self) -> Changed:
        """``{plane_id, cell_id, source}``."""
        return interactions.on_update_cell(self)

    def on_delete_cell(self) -> Changed:
        """``{plane_id, cell_id}``."""
        return interactions.on_delete_cell(self)

    def on_move_cell(self) -> Changed:
        """``{plane_id, cell_id, to_plane_id, index}``."""
        return interactions.on_move_cell(self)

    def on_reorder_cells(self) -> Changed:
        """``{plane_id, cell_ids}``."""
        return interactions.on_reorder_cells(self)

    def on_set_meta(self) -> Changed:
        """``{plane_id, meta}``."""
        return interactions.on_set_meta(self)
