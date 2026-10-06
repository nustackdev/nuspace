"""Ops on a switch cell: its value set and read, from any plane, by the cell's id.

Find a cell by its name with :func:`nuspace.ops.cell_named`. A write is one
commit to the state store and a running cell shows it. A read is bare: its
caller brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.shapes import Space

from .snippet import Flag


__all__ = ["search", "set_value", "value_of"]


_ON, _OFF = {"on", "true", "yes"}, {"off", "false", "no"}


def _same(value: bool, query: str) -> bool:
    word = str(query).strip().lower()
    return word in (_ON if value else _OFF)


#: Whether ``query`` names ``value``: on, true or yes for on; off, false or no for off.
Same = nu.host(_same, name="SwitchSame")


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


def search(query: nu.StrArg, cell: nu.StrArg) -> nu.Nu:
    """A switch cell searched: ``[{excerpt}]`` when ``query`` names its state (on, true, yes; off, false, no), else ``[]``.

    The excerpt is the cell's name and its value, eg ``budget: 42``. A value
    never set is nothing to find.
    """
    value = ops.cell_state(cell, Flag.value)
    hit = nu.List.of(
        nu.Dict.of(excerpt=Space.cells[cell].name.fallback("") + ": " + nu.If(value, "on", "off"))
    )
    found = nu.If(Same(value, query), hit, [])
    return nu.If(ops.cell_state(cell, Flag.value.exists()), found, [])
