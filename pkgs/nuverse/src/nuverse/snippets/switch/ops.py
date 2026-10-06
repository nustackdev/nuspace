"""Ops on a switch cell: its value set and read, from any plane, by the cell's id.

Find a cell by its name with :func:`nuspace.ops.cell_named`. A write is one
commit to the state store and a running cell shows it. A read is bare: its
caller brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops

from .snippet import Flag


__all__ = ["set_value", "value_of"]


def set_value(cell_id: nu.StrArg, value: nu.BoolArg) -> nu.Nu:
    """Set a switch cell's value. A no-op when the cell is missing.

    Args:
        cell_id: The switch cell.
        value: Its value now.
    """
    kept = ops.cell_state(cell_id, Flag.value.set(value))
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def value_of(cell_id: nu.StrArg) -> nu.Nu:
    """A switch cell's value, ``False`` before one is set. Bare: wrap it in ``ops.snapshot``.

    Args:
        cell_id: The switch cell.
    """
    return ops.cell_state(cell_id, Flag.value.fallback(False))
