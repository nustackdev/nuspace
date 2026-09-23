"""Layer three: the host composes the system.

- :mod:`.registry`: extensions, their discovery, and the merged registry.
- :mod:`.space`: :func:`open_space`, the whole system in one term.
- :mod:`.cli`: the ``nuspace`` command. Not imported here: workers import
  :mod:`nuspace`, and the command line is no business of theirs.
"""

from .registry import GROUP, Extension, Registry, RegistryWarning, discover
from .space import open_space, space_registry


__all__ = [
    "GROUP",
    "Extension",
    "Registry",
    "RegistryWarning",
    "discover",
    "open_space",
    "space_registry",
]
