"""Layer zero: the extension system, what a package plugs into a space with.

- :mod:`.specs`: :class:`Plane`, what ``+`` creates, and :class:`Cell`,
  what ``/`` inserts. Plain data. :data:`EMPTY`, the plane every space has.
- :mod:`.registry`: :class:`Extension`, a bundle of them and of content
  kinds (:class:`nuspace.Content`), found through the
  ``nuspace.extensions`` entry point group, and the merged :class:`Registry`
  a space opens with.

An extension imports from here, and nothing here imports the rest of nuspace.
"""

from .registry import (
    GROUP,
    Extension,
    Registry,
    RegistryWarning,
    discover,
    qualified,
    registered_name,
    short_name,
    space_registry,
)
from .specs import EMPTY, TEXT, Cell, Plane


__all__ = [
    "EMPTY",
    "GROUP",
    "TEXT",
    "Cell",
    "Extension",
    "Plane",
    "Registry",
    "RegistryWarning",
    "discover",
    "qualified",
    "registered_name",
    "short_name",
    "space_registry",
]
