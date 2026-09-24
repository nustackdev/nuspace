"""The viewer as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders the open planes'
cells, one pane per plane.
It never asks what kind of plane it draws; the one bit it reads off the
plane is ``editable``, which arrives with the page like anything else.

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

    from nu.lang import BoolArg, ListArg, Nu, StrArg
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

    def set_page(
        self,
        page_id: StrArg,
        *,
        title: StrArg,
        editable: BoolArg,
        blocks: ListArg[dict],
    ) -> Nu:
        """Replace what one pane draws: one plane, and its cells in order."""
        return interactions.set_page(self, page_id, title=title, editable=editable, cells=blocks)

    def set_status(self, page_id: StrArg, statuses: ListArg[dict]) -> Nu:
        """Patch what one pane says about its cells."""
        return interactions.set_status(self, page_id, statuses)

    def on_open(self) -> Changed:
        """``{page_ids}``, the full ordered list."""
        return interactions.on_open(self)

    def on_create_section(self) -> Changed:
        """``{page_id, section_id, name, index}``."""
        return interactions.on_create_cell(self)

    def on_update_section(self) -> Changed:
        """``{page_id, section_id, source}``."""
        return interactions.on_update_cell(self)

    def on_delete_section(self) -> Changed:
        """``{page_id, section_id}``."""
        return interactions.on_delete_cell(self)

    def on_move_section(self) -> Changed:
        """``{page_id, section_id, to_page_id, index}``."""
        return interactions.on_move_cell(self)

    def on_reorder_sections(self) -> Changed:
        """``{page_id, section_ids}``."""
        return interactions.on_reorder_cells(self)
