"""``nuspace.state``: the ops over State (``state.db``) a place cannot do as a ref verb.

Programs read and write State through places (``nuspace.at``,
``nuspace.here``): plain nu on the refs a place builds. What is left here
wipes a whole scope, its plain slots and its items of every content kind,
which means walking the installed kinds. The kinds are read when the op is
built, so the walk is a fixed list, never a scan of the space.

Each op writes State and reads Space (whether the cell or plane is
there), so ``nuspace.atomic`` commits it to State and reads Space from a
snapshot. A removed cell or plane keeps its state, so clearing one works.
"""

from __future__ import annotations

import nu
from nuspace.shapes.space import Space
from nuspace.shapes.state import State
from nuspace.specs.registry import content_specs
from nuspace.utils.checks import row_known


__all__ = ["clear_cell", "clear_plane", "clear_space"]


def _kinds() -> tuple[str, ...]:
    """The installed content kinds' names, as the store keys them."""
    return tuple(content_specs())


def clear_cell(cell: nu.StrArg) -> nu.Nu:
    """Wipe a cell's state: its plain slots and its items of every installed kind.

    ``State.cells[cell]`` and each ``content_cells[kind].cells[cell]``
    erased. Resets a program to its first run. Cost: O(its slots + its
    items), plus one point read per installed kind.

    Raises:
        Missing: No cell with that id.
    """
    items = [State.content_cells[kind].cells[cell].erase() for kind in _kinds()]
    return (
        row_known(Space.cells, cell, "cell")
        >> State.cells[cell].erase()
        >> nu.Sequential(nu.Noop(), *items)
    )


def clear_plane(plane: nu.StrArg) -> nu.Nu:
    """Wipe a plane's state, the one its cells share: plain slots and items of every kind.

    ``State.planes[plane]`` and each ``content_planes[kind].planes[plane]``
    erased. Its cells' own state stays: :func:`clear_cell`. Cost: O(its
    slots + its items), plus one point read per installed kind.

    Raises:
        Missing: No plane with that id.
    """
    items = [State.content_planes[kind].planes[plane].erase() for kind in _kinds()]
    return (
        row_known(Space.planes, plane, "plane")
        >> State.planes[plane].erase()
        >> nu.Sequential(nu.Noop(), *items)
    )


def clear_space() -> nu.Nu:
    """Wipe the space's own state: ``State.space`` emptied and each ``content_space[kind]`` erased.

    Cell and plane state stay. Cost: O(its slots + its items). Never raises.
    """
    items = [State.content_space[kind].erase() for kind in _kinds()]
    return State.space.clear() >> nu.Sequential(nu.Noop(), *items)
