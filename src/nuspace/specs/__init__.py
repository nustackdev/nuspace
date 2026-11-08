"""``nuspace.specs``: the recipes planes and cells are made from, and what a package plugs in.

- :mod:`.specs`: one spec per extension point, plain data.
  :class:`PlaneSpec`, what ``+`` creates (with :class:`WebOptions` when it
  shows on the web), :class:`CellSpec`, what ``/`` inserts, and
  :class:`ContentSpec`, a content kind cells keep items of.
  :data:`EMPTY_PLANE`, the plane every space has. :class:`SpecCells`, where
  a spec plane keeps its cells' ids.
- :mod:`.registry`: :class:`Extension`, a package's bundle of them, found
  through the ``nuspace.extensions`` entry point group and nowhere else,
  and the merged :class:`Registry` a space opens with. Any process finds an
  installed spec or content kind by its name (:func:`plane_spec`,
  :func:`cell_spec`, :func:`content_spec`).
- :mod:`.ops`: :func:`add_plane` and :func:`add_cell`, making planes and
  cells from specs.
"""

# Last: the ops import nuspace.ops, which reads the registry above.
from .ops import add_cell, add_plane
from .registry import (
    GROUP,
    Extension,
    Registry,
    RegistryWarning,
    cell_spec,
    content_spec,
    content_specs,
    discover,
    kind_name,
    plane_spec,
    qualified,
    registered_name,
    short_name,
    space_registry,
)
from .specs import EMPTY_PLANE, CellSpec, ContentSpec, PlaneSpec, SpecCells, WebOptions


__all__ = [
    "EMPTY_PLANE",
    "GROUP",
    "CellSpec",
    "ContentSpec",
    "Extension",
    "PlaneSpec",
    "Registry",
    "RegistryWarning",
    "SpecCells",
    "WebOptions",
    "add_cell",
    "add_plane",
    "cell_spec",
    "content_spec",
    "content_specs",
    "discover",
    "kind_name",
    "plane_spec",
    "qualified",
    "registered_name",
    "short_name",
    "space_registry",
]
