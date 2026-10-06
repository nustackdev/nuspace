"""Ops on a slider cell: its value set and read, from any plane, by the cell's id.

Find a cell by its name with :func:`nuspace.ops.cell_named`. A write is one
commit to the state store and a running cell shows it. A read is bare: its
caller brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.shapes import Space

from ..number.ops import Same, Shown
from .snippet import Level


__all__ = ["search", "set_value", "value_of"]


def set_value(cell_id: nu.StrArg, value: nu.FloatArg) -> nu.Nu:
    """Set a slider cell's value. A no-op when the cell is missing.

    Args:
        cell_id: The slider cell.
        value: Its value now.
    """
    kept = ops.cell_state(cell_id, Level.value.set(value))
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def value_of(cell_id: nu.StrArg) -> nu.Nu:
    """A slider cell's value, ``0.0`` before one is set. Bare: wrap it in ``ops.snapshot``.

    Args:
        cell_id: The slider cell.
    """
    return ops.cell_state(cell_id, Level.value.fallback(0.0))


def search(query: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """A slider cell searched: ``[{excerpt}]`` when ``query``, read as a number, is its number, else ``[]``.

    The excerpt is the cell's name and its value, eg ``budget: 42``. A value
    never set is nothing to find.
    """
    value = ops.cell_state(cell, Level.value)
    hit = nu.List.of(nu.Dict.of(excerpt=Space.cells[cell].name.fallback("") + ": " + Shown(value)))
    found = nu.If(Same(value, query), hit, [])
    return nu.If(ops.cell_state(cell, Level.value.exists()), found, [])
