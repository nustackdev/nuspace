"""Layer zero: the extension system, what a package plugs into a space with.

- :mod:`.specs`: :class:`Plane`, what ``+`` creates, and :class:`Snippet`,
  what ``/`` inserts. Plain data.
- :mod:`.registry`: :class:`Extension`, a bundle of them, found through the
  ``nuspace.extensions`` entry point group, and the merged :class:`Registry`
  a space opens with.

An extension imports from here, and nothing here imports the rest of nuspace.
"""

from .registry import GROUP, Extension, Registry, RegistryWarning, discover, space_registry
from .specs import TEXT, Plane, Snippet


__all__ = [
    "GROUP",
    "TEXT",
    "Extension",
    "Plane",
    "Registry",
    "RegistryWarning",
    "Snippet",
    "discover",
    "space_registry",
]
