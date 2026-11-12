"""nuspace: a space that runs nu programs as planes and cells.

The top level holds the everyday names only:

- the roots: :class:`Space` (what the space is) and :class:`State` (what
  programs keep); the record shapes are under :mod:`nuspace.shapes`.
- the core op modules: ``nuspace.plane``, ``.cell``, ``.plane_run``,
  ``.cell_run``, ``.worker``, ``.state``. Write the module in front,
  ``nuspace.plane.add(...)``. They are attributes, not submodules:
  ``import nuspace.plane`` does not work. ``nuspace.state`` (the ops) and
  ``nuspace.State`` (the root) differ by case only, as python modules and
  classes do.
- places: ``nuspace.at``, ``nuspace.here``.
- brackets: ``nuspace.atomic``, ``nuspace.bracketed``.
- ``nuspace.specs`` (PlaneSpec, CellSpec, the registry, add_plane,
  add_cell) and ``nuspace.errors`` (what an op raises).

``nuspace.kernel``, ``nuspace.system.*``, ``nuspace.web``,
``nuspace.host`` and ``nuspace.utils`` stay namespaced.

Workers import this package: nothing here may pull in a server.
"""

from nuspace import errors, specs
from nuspace.ops import cell, cell_run, plane, plane_run, state, worker
from nuspace.ops.brackets import atomic, bracketed
from nuspace.places import at, here
from nuspace.shapes import Space, State


__all__ = [
    "Space",
    "State",
    "at",
    "atomic",
    "bracketed",
    "cell",
    "cell_run",
    "errors",
    "here",
    "plane",
    "plane_run",
    "specs",
    "state",
    "worker",
]
