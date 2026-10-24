"""Reroot: land a program's state refs under the plane and cell running it.

A program names :class:`~nuspace.shapes.state.CellState` and
:class:`~nuspace.shapes.state.PlaneState` slots bare. At load the kernel
splices every such chain under its owner's ``state``:

========================  ==========================================
chain rooted at           lands at
========================  ==========================================
a ``CellState`` subclass  ``States.cells[cell]``
a ``PlaneState`` subclass ``States.planes[plane].state``
``CellContent``           ``States.contents[kind].cells[cell]``
``PlaneContent``          ``States.contents[kind].planes[plane]``
anything else             left alone: another store, Space, ui refs
========================  ==========================================

An item chain (``TextContent.cell("summary")``, :mod:`nuspace.content`)
lands under its own kind, so one splice per kind the term names: the kinds
are read off the term's chain roots, never off a registry, so the rewrite
needs nothing but the two ids.

Explicit bases rather than "anything not rooted at Space", because a movies
db ref a program brings along must not move. The splice itself is
``nu.shape.reroot``: the chain resolves one level deeper and picks up
States' tag, so it routes to the state store's navigator, never Space's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.domains.shape import StructuredRef

from .contents import CONTENT_KIND, CellContent, PlaneContent
from .state import CellState, PlaneState
from .states import States


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["Reroot", "reroot", "reroot_base", "reroot_contents"]


def _foreign(base: type[nu.Shape]) -> Callable[[StructuredRef], bool]:
    """A ``rooted`` predicate exempting every chain not rooted at ``base``."""

    def rooted(ref: StructuredRef) -> bool:
        shape = nu.shape.root_shape(ref)
        return not (isinstance(shape, type) and issubclass(shape, base))

    return rooted


def reroot_base(term: nu.Nu, base: type[nu.Shape], at: nu.Nu) -> nu.Nu:
    """``term`` with the chains rooted at a ``base`` subclass spliced under ``at``.

    The one splice both bases go through, exposed so an op can land a
    program's state somewhere other than its own cell (eg a sibling's).

    Args:
        term: Any Nu term.
        base: :class:`CellState` or :class:`PlaneState`. Chains rooted at
            any other shape are left alone.
        at: The ref the chains land under, eg ``States.planes[p].state``.

    Returns:
        The rewritten term, or ``term`` itself when nothing matched.
    """
    return nu.shape.reroot(term, at, rooted=_foreign(base))


def _kind_of(ref: StructuredRef, base: type[nu.Shape]) -> str | None:
    """The kind a chain root of an item relative to ``base`` names, None for any other chain."""
    if nu.shape.root_shape(ref) is not base:
        return None
    return nu.tree.payload(ref).get(CONTENT_KIND)  # type: ignore[return-value]


def _chain_root(node: nu.Nu) -> bool:
    """Whether ``node`` is a chain root: a ref whose parent is the anchor."""
    return isinstance(node, StructuredRef) and not isinstance(
        nu.tree.children(node)[0], StructuredRef
    )


def reroot_contents(term: nu.Nu, base: type[nu.Shape], at: nu.StrArg) -> nu.Nu:
    """``term`` with its item chains relative to ``base`` landed under scope ``at``, per kind.

    Args:
        term: Any Nu term.
        base: :class:`~.contents.CellContent` or
            :class:`~.contents.PlaneContent`, which says the scope's level.
        at: The cell or plane id the items land under.

    Returns:
        The rewritten term, or ``term`` itself when it names no such item.
    """
    slot = "cells" if base is CellContent else "planes"
    roots = nu.tree.find(term, _chain_root)
    kinds = sorted({k for k in (_kind_of(r, base) for r in roots) if k is not None})
    for kind in kinds:

        def rooted(ref: StructuredRef, kind: str = kind) -> bool:
            return _kind_of(ref, base) != kind

        under = getattr(States.contents[kind], slot)[at]
        term = nu.shape.reroot(term, under, rooted=rooted)
    return term


def reroot(term: nu.Nu, plane: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """``term`` with its cell state and items under ``cell``, its plane's under ``plane``.

    Both ids, since the two land apart: a cell's state is keyed by the cell
    alone, the state it shares by its plane.

    Args:
        term: Any Nu term, typically a loaded program.
        plane: The plane id. Any ``StrArg``, since the kernel binds it at run
            time (eg ``nu.StrRef``).
        cell: The cell id, same.

    Returns:
        The rewritten term. ``term`` itself is untouched, and a term with no
        state chains comes back as the same object.
    """
    term = reroot_base(term, CellState, States.cells[cell])
    term = reroot_base(term, PlaneState, States.planes[plane].state)
    term = reroot_contents(term, CellContent, cell)
    return reroot_contents(term, PlaneContent, plane)


class Reroot:
    """:func:`reroot` with its plane and cell fixed, as a ``Nu -> Nu`` transform.

    A class rather than a closure because it is pickled into a worker with
    the body that loads the program.

    Args:
        plane: The plane id, as a ``StrArg``.
        cell: The cell id, as a ``StrArg``.
    """

    __slots__ = ("cell", "plane")

    def __init__(self, plane: nu.StrArg, cell: nu.StrArg) -> None:
        self.plane = plane
        self.cell = cell

    def __call__(self, term: nu.Nu) -> nu.Nu:
        """The term, its state chains landing under this plane and cell."""
        return reroot(term, self.plane, self.cell)
