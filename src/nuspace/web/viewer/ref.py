"""The viewer and its panes as nodes on the browser's tree.

:class:`ViewerRef` is the desk area. It keeps only what every pane shares:
``cell_specs``, the ``/`` menu's entries in order, each with its classes and
the classes it is the default of, which is how the input line finds what
typing creates. It is mounted with them when the shell boots (D19), since the
Cells are the host's registry and the shell is a static class. It hears
``planes.open``, the tab's layout, and every cell's own ui hangs under it at
``viewer/cells/<cell>``.

:class:`PaneRef` is one open plane, at ``viewer/panes/<plane>``: everything
that pane shows, and everything it says. Its first write mounts it, the
feed erases it when the pane closes. It never asks what kind of plane it
draws; what it reads off the plane is its head (name, icon, key, ``system``)
and its web flags (``editable``, ``width``), and those go back through the
pane's own ops.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import Self

from nuspace.specs import registered_name
from nuspace.web.utils import PANES, SpaceRef
from nuspace.web.viewer import interactions


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nu.lang import BoolArg, ListArg, Nu, StrArg
    from nuspace.specs import CellSpec
    from nustd.ui.core import Changed, Ref


__all__ = ["PaneRef", "PanesRef", "ViewerRef", "pane_ref", "slash_entries"]


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
    """The desk area: what every pane shares, as one browser node."""

    _wire_type: ClassVar[str] = "ViewerRef"

    @classmethod
    def slot(cls, *, cell_specs: Sequence[Mapping[str, object]] | None = None) -> Self:
        """Mount the viewer, seeded with the ``/`` menu."""
        return super().slot(cell_specs=[dict(s) for s in cell_specs or ()])

    def on_open(self) -> Changed:
        """``{plane_ids, params}``, the full ordered list."""
        return interactions.on_open(self)


class PanesRef(SpaceRef):
    """The level every open pane hangs under. Holds nothing, draws nothing."""

    _wire_type: ClassVar[str] = "PanesRef"


class PaneRef(SpaceRef):
    """One open plane, as one browser node: its head, cells, statuses and trail."""

    _wire_type: ClassVar[str] = "PaneRef"

    def set_head(
        self,
        *,
        title: StrArg,
        icon: StrArg,
        key: StrArg,
        system: BoolArg,
        editable: BoolArg,
        width: StrArg,
    ) -> Nu:
        """Replace how the pane heads its plane. Clears an absent."""
        return interactions.set_head(
            self, title=title, icon=icon, key=key, system=system, editable=editable, width=width
        )

    def set_cells(self, cells: ListArg[dict]) -> Nu:
        """Replace the pane's cells, in order."""
        return interactions.set_cells(self, cells)

    def set_absent(self, reason: StrArg) -> Nu:
        """Say the pane has nothing to draw: its plane is missing or headless."""
        return interactions.set_absent(self, reason)

    def set_status(self, statuses: ListArg[dict]) -> Nu:
        """Say what each of the pane's cells is doing."""
        return interactions.set_status(self, statuses)

    def set_trail(self, trail: ListArg[dict]) -> Nu:
        """Say which planes sit above the pane's, top first."""
        return interactions.set_trail(self, trail)

    def on_rename_plane(self) -> Changed:
        """``{title}``."""
        return interactions.on_rename_plane(self)

    def on_set_icon(self) -> Changed:
        """``{icon}``."""
        return interactions.on_set_icon(self)

    def on_delete_plane(self) -> Changed:
        """``{}``."""
        return interactions.on_delete_plane(self)

    def on_set_plane_key(self) -> Changed:
        """``{key}``."""
        return interactions.on_set_plane_key(self)

    def on_remove_plane_key(self) -> Changed:
        """``{}``."""
        return interactions.on_remove_plane_key(self)

    def on_set_web(self) -> Changed:
        """``{flags}``."""
        return interactions.on_set_web(self)

    def on_restart_plane(self) -> Changed:
        """``{}``."""
        return interactions.on_restart_plane(self)

    def on_create_cell(self) -> Changed:
        """``{cell_id, name, before?, after?}``."""
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

    def on_set_cell_key(self) -> Changed:
        """``{cell_id, key}``."""
        return interactions.on_set_cell_key(self)

    def on_remove_cell_key(self) -> Changed:
        """``{cell_id}``."""
        return interactions.on_remove_cell_key(self)


def pane_ref(viewer: Ref, plane: StrArg) -> PaneRef:
    """The pane on ``plane`` under ``viewer``: ``viewer/panes/<plane>``.

    Args:
        viewer: The ref panes are drawn on, bound to its place on the shell.
        plane: The plane id, any ``StrArg`` (eg ``Here.plane``).
    """
    return PaneRef(plane, parent_ref=PanesRef(PANES, parent_ref=viewer))
