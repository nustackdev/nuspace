"""Layer zero: the extension system, what a package plugs into a space with.

- :mod:`.specs`: one spec per extension point, plain data.
  :class:`PlaneSpec`, what ``+`` creates, :class:`CellSpec`, what ``/``
  inserts, and :class:`ContentSpec`, a content kind
  (:class:`nuspace.Content`) cells keep items of. :data:`EMPTY_PLANE`, the
  plane every space has.
- :mod:`.registry`: :class:`Extension`, a package's bundle of them, found
  through the ``nuspace.extensions`` entry point group and nowhere else,
  and the merged :class:`Registry` a space opens with. Any process finds
  an installed content kind by its name (:func:`content_spec`).

An extension imports from here, and nothing here imports the rest of nuspace.
"""

from .registry import (
    GROUP,
    Extension,
    Registry,
    RegistryWarning,
    content_spec,
    content_specs,
    discover,
    kind_name,
    qualified,
    registered_name,
    short_name,
    space_registry,
)
from .specs import EMPTY_PLANE, TEXT_CELL, CellSpec, ContentSpec, PlaneSpec


__all__ = [
    "EMPTY_PLANE",
    "GROUP",
    "TEXT_CELL",
    "CellSpec",
    "ContentSpec",
    "Extension",
    "PlaneSpec",
    "Registry",
    "RegistryWarning",
    "content_spec",
    "content_specs",
    "discover",
    "kind_name",
    "qualified",
    "registered_name",
    "short_name",
    "space_registry",
]
