"""nuspace: runs Nu programs as a space of planes and cells.

What a host and a program need, without knowing the layers:

- :func:`open_space`, and :class:`Extension`, :class:`Plane`, :class:`Snippet`
  to register (the store's own plane shape is ``shapes.Plane``);
- :class:`CellState`, :class:`PlaneState`, so a program says
  ``class Tick(nuspace.CellState)``;
- :mod:`ops`, and the few a host reaches for first: :func:`boot`,
  :func:`unboot`, :func:`supervise`, :func:`env`.

Workers import this package: nothing here may pull in a server.
"""

from nuspace import ops, shapes
from nuspace.host import Extension, open_space
from nuspace.ops import Plane, Snippet, env
from nuspace.shapes import CellState, PlaneState, Space
from nuspace.system.services import boot, supervise, unboot, unsupervise


__all__ = [
    "CellState",
    "Extension",
    "Plane",
    "PlaneState",
    "Snippet",
    "Space",
    "boot",
    "env",
    "open_space",
    "ops",
    "shapes",
    "supervise",
    "unboot",
    "unsupervise",
]
