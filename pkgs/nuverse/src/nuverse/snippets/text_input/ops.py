"""Ops on a text input cell: its value set and read, from any plane, by the cell's id.

Find a cell by its name with :func:`nuspace.ops.cell_named`. A write is one
commit to the state store and a running cell shows it. A read is bare: its
caller brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.shapes import Space

from .snippet import Line


__all__ = ["search", "set_value", "value_of"]


def set_value(cell_id: nu.StrArg, value: nu.StrArg) -> nu.Nu:
    """Set a text input cell's value. A no-op when the cell is missing.

    Args:
        cell_id: The text input cell.
        value: Its value now.
    """
    kept = ops.cell_state(cell_id, Line.value.set(value))
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def value_of(cell_id: nu.StrArg) -> nu.Nu:
    """A text input cell's value, ``""`` before one is set. Bare: wrap it in ``ops.snapshot``.

    Args:
        cell_id: The text input cell.
    """
    return ops.cell_state(cell_id, Line.value.fallback(""))


def search(query: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """A text input cell searched: ``[{excerpt}]`` when its text is ``query``, trimmed and ignoring case, else ``[]``.

    The excerpt is the cell's name and its value, eg ``budget: 42``. A value
    never set is nothing to find.
    """
    value = ops.cell_state(cell, Line.value)
    hit = nu.List.of(nu.Dict.of(excerpt=Space.cells[cell].name.fallback("") + ": " + nu.str(value)))
    found = nu.If(nu.Str(value).strip().lower() == nu.Str(query).strip().lower(), hit, [])
    return nu.If(ops.cell_state(cell, Line.value.exists()), found, [])
