"""Reroot: land a program's state refs under the plane and cell running it.

A program names :class:`~nuspace.shapes.state.CellState` and
:class:`~nuspace.shapes.state.PlaneState` slots bare. At load the kernel
splices every such chain under its owner's ``state``:

========================  ==========================================
chain rooted at           lands at
========================  ==========================================
a ``CellState`` subclass  ``Space.planes[plane].cells[cell].state``
a ``PlaneState`` subclass ``Space.planes[plane].state``
anything else             left alone: another store, Space, ui refs
========================  ==========================================

Explicit bases rather than "anything not rooted at Space", because a movies
db ref a program brings along must not move. The splice itself is
``nu.shape.reroot``: the chain resolves one level deeper and picks up
Space's tag, so it routes to the store's navigator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from .space import Space
from .state import CellState, PlaneState


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape.refs.base import StructuredRef


__all__ = ["Reroot", "reroot"]


def _foreign(base: type[nu.Shape]) -> Callable[[StructuredRef], bool]:
    """A ``rooted`` predicate exempting every chain not rooted at ``base``."""

    def rooted(ref: StructuredRef) -> bool:
        shape = nu.shape.root_shape(ref)
        return not (isinstance(shape, type) and issubclass(shape, base))

    return rooted


def reroot(term: nu.Nu, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """``term`` with its state chains spliced under ``plane`` and ``cell``.

    Args:
        term: any Nu term, typically a loaded program.
        plane: the plane id. Any ``StrArg``, since the kernel binds it at run
            time (eg ``nu.StrAttrRef``).
        cell: the cell id, same.

    Returns:
        The rewritten term. ``term`` itself is untouched, and a term with no
        state chains comes back as the same object.
    """
    row = Space.planes[plane]
    term = nu.shape.reroot(term, row.cells[cell].state, rooted=_foreign(CellState))
    return nu.shape.reroot(term, row.state, rooted=_foreign(PlaneState))


class Reroot:
    """:func:`reroot` with its plane and cell fixed, as a ``Nu -> Nu`` transform.

    A class rather than a closure because it is pickled into a worker with
    the body that loads the program.

    Args:
        plane: the plane id, as a ``StrArg``.
        cell: the cell id, as a ``StrArg``.
    """

    __slots__ = ("cell", "plane")

    def __init__(self, plane: nu.StrArg, cell: nu.StrArg) -> None:
        self.plane = plane
        self.cell = cell

    def __call__(self, term: nu.Nu) -> nu.Nu:
        """The term, its state chains landing under this plane and cell."""
        return reroot(term, self.plane, self.cell)
