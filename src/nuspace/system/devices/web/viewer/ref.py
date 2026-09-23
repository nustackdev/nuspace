"""The viewer as one node on the browser's tree.

A component ref like ``ButtonRef``, only wider: it renders one plane's cells.
It never asks what kind of plane it draws; the one bit it reads off the
plane is ``editable``, which arrives with the page like anything else.

``starters`` is the one prop it is mounted with: what a cell made from each
``/`` entry starts as (D19). Seeded when the shell boots, since the snippets
are the host's registry and the shell is a static class.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.system.devices.web.utils import SpaceRef
from nuspace.system.devices.web.viewer import interactions


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from nu.lang import BoolArg, ListArg, Nu, StrArg
    from nuspace.ops import Snippet
    from nustd.ui.core import Changed


__all__ = ["ViewerRef", "starters"]


def starters(snippets: Iterable[Snippet]) -> dict[str, str]:
    """What a cell made from each snippet starts as, keyed by snippet name."""
    return {snippet.name: snippet.source for snippet in snippets}


class ViewerRef(SpaceRef):
    """One plane's cells, as one browser node."""

    _wire_type: ClassVar[str] = "ViewerRef"

    @classmethod
    def slot(cls, *, starters: Mapping[str, str] | None = None) -> Self:
        """Mount the viewer, seeded with what a new cell starts as."""
        return super().slot(starters=dict(starters or {}))

    def set_page(
        self,
        page_id: StrArg,
        *,
        title: StrArg,
        editable: BoolArg,
        blocks: ListArg[dict],
    ) -> Nu:
        """Replace what is drawn: one plane, and its cells in order."""
        return interactions.set_page(self, page_id, title=title, editable=editable, cells=blocks)

    def set_status(self, statuses: ListArg[dict]) -> Nu:
        """Patch what the viewer says about its cells."""
        return interactions.set_status(self, statuses)

    def on_select(self) -> Changed:
        """``{page_id}``."""
        return interactions.on_select(self)

    def on_create_section(self) -> Changed:
        """``{page_id, section_id, name, tpl, source, index}``."""
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
