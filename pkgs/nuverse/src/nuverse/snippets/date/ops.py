"""Ops on a date cell: its value set and read, from any plane, by the cell's id.

Find a cell by its name with :func:`nuspace.ops.cell_named`. A write is one
commit to the state store and a running cell shows it. A read is bare: its
caller brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.shapes import Space

from .snippet import Day


__all__ = ["search", "set_value", "value_of"]


def set_value(cell_id: nu.StrArg, value: nu.Arg) -> nu.Nu:
    """Set a date cell's value. A no-op when the cell is missing.

    Args:
        cell_id: The date cell.
        value: Its value now.
    """
    kept = ops.cell_state(cell_id, Day.value.set(value))
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def value_of(cell_id: nu.StrArg) -> nu.Nu:
    """A date cell's value, EMPTY before one is set. Bare: wrap it in ``ops.snapshot``.

    Args:
        cell_id: The date cell.
    """
    return ops.cell_state(cell_id, Day.value)


def search(query: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """A date cell searched: ``[{excerpt}]`` when its date is ``query``, ISO ``YYYY-MM-DD``, else ``[]``.

    The excerpt is the cell's name and its value, eg ``budget: 42``. A value
    never set is nothing to find.
    """
    value = ops.cell_state(cell, Day.value)
    hit = nu.List.of(
        nu.Dict.of(excerpt=Space.cells[cell].name.fallback("") + ": " + nu.ToStr(value))
    )
    found = nu.If(nu.Str(nu.ToStr(value)) == nu.Str(query).strip(), hit, [])
    return nu.If(ops.cell_state(cell, Day.value.exists()), found, [])
