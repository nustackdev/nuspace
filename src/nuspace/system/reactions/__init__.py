"""``nuspace.system.reactions``: the system plane that runs a plane when something changes.

- ops: :func:`add`, :func:`remove`, :func:`clear`; :func:`source`, a reaction's prog.
- :mod:`.plane`: the plane's ids, its park cell, :func:`react` (a reaction's program) and :func:`up_plane`.
- shapes: :class:`Registry` (by plane), :class:`Reaction` (a reaction's plane and run).
"""

from .ops import add, clear, remove, source
from .plane import PARK, PLANE, react, registry, up_plane
from .shapes import Reaction, ReactionIds, Registry


__all__ = [
    "PARK",
    "PLANE",
    "Reaction",
    "ReactionIds",
    "Registry",
    "add",
    "clear",
    "react",
    "registry",
    "remove",
    "source",
    "up_plane",
]
