"""A unit converter: two amounts, either one typed, the other worked out.

What the cell keeps is the amount in its kind's base unit (metres,
kilograms, kelvin, seconds), so typing on either side writes the same slot
and both sides are drawn from it. That is the whole trick: one value
stored, two views of it, both editable.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["KINDS", "Convert", "out"]


#: Each kind's units as ``unit: [scale, offset]``: ``base = amount * scale + offset``.
KINDS: dict[str, dict[str, list[float]]] = {
    "Length": {
        "m": [1.0, 0.0],
        "km": [1000.0, 0.0],
        "cm": [0.01, 0.0],
        "mi": [1609.344, 0.0],
        "ft": [0.3048, 0.0],
        "in": [0.0254, 0.0],
    },
    "Mass": {
        "kg": [1.0, 0.0],
        "g": [0.001, 0.0],
        "lb": [0.45359237, 0.0],
        "oz": [0.028349523125, 0.0],
    },
    "Temperature": {
        "°C": [1.0, 273.15],
        "°F": [5 / 9, 459.67 * 5 / 9],
        "K": [1.0, 0.0],
    },
    "Time": {
        "s": [1.0, 0.0],
        "min": [60.0, 0.0],
        "h": [3600.0, 0.0],
        "day": [86400.0, 0.0],
    },
}


def _round(x: float) -> float:
    return float(f"{float(x):.6g}")


#: A number cut to six significant digits, so 1 mi reads 1.60934, not 1.6093440000000001.
Rounded = nu.host(_round, name="ConverterRounded")


class Convert(nuspace.CellState):
    """The converter's state: the kind, a unit each side, and the amount in the base unit."""

    kind = nustd.kv.StrRef.slot()
    left = nustd.kv.StrRef.slot()
    right = nustd.kv.StrRef.slot()
    base = nustd.kv.FloatRef.slot()


class Side(nustd.ui.Row):
    amount = nustd.ui.NumberInputRef.slot(step=0.1)
    unit = nustd.ui.SelectRef.slot()


class Box(nustd.ui.Column):
    kind = nustd.ui.SelectRef.slot(options=list(KINDS))
    left = Side.slot(gap=2)
    right = Side.slot(gap=2)


def out() -> nu.Nu:
    """The converter, for as long as the cell runs."""
    kinds = nu.Dict(nu.Literal(KINDS))
    kind = Convert.kind.fallback("Length")
    units = nu.Dict(kinds[kind])
    names = nu.list(units.keys())
    left = Convert.left.fallback(nu.str(names[0]))
    right = Convert.right.fallback(nu.str(names[1]))

    def scale(unit: nu.Nu) -> nu.Float:
        return nu.Float(nu.List(units[unit])[0])

    def offset(unit: nu.Nu) -> nu.Float:
        return nu.Float(nu.List(units[unit])[1])

    def amount(unit: nu.Nu) -> nu.Nu:
        return Rounded((Convert.base.fallback(1.0) - offset(unit)) / scale(unit))

    def typed(side: nu.Nu, unit: nu.Nu) -> nu.Nu:
        return Convert.base.set(nu.ToFloat(side.amount) * scale(unit) + offset(unit))

    def show() -> nu.Nu:
        return (
            Box.kind.set(kind)
            >> Box.left.unit.set_options(names)
            >> Box.right.unit.set_options(names)
            >> Box.left.unit.set(left)
            >> Box.right.unit.set(right)
            >> Box.left.amount.set_value(amount(left))
            >> Box.right.amount.set_value(amount(right))
        )

    def rekind() -> nu.Nu:
        # Another kind: its first two units, one of the left one.
        picked = nu.Str(Box.kind)
        units_of = nu.Dict(kinds[picked])
        first = nu.list(units_of.keys())
        one = nu.List(units_of[first[0]])
        return (
            Convert.kind.set(picked)
            >> Convert.left.set(nu.str(first[0]))
            >> Convert.right.set(nu.str(first[1]))
            >> Convert.base.set(nu.Float(one[0]) + nu.Float(one[1]))
        )

    # Anything stored changed, here or in another tab: draw it all again.
    stored = (Convert.kind, Convert.left, Convert.right, Convert.base)
    return ops.bracketed(
        show()
        >> nu.ParallelAsync(
            nu.ReactForever(Box.kind.on_change(), rekind()),
            nu.ReactForever(Box.left.unit.on_change(), Convert.left.set(nu.ToStr(Box.left.unit))),
            nu.ReactForever(
                Box.right.unit.on_change(), Convert.right.set(nu.ToStr(Box.right.unit))
            ),
            nu.ReactForever(Box.left.amount.on_change(), typed(Box.left, left)),
            nu.ReactForever(Box.right.amount.on_change(), typed(Box.right, right)),
            *(nu.ReactForever(slot.on_change(), show()) for slot in stored),
        )
    )
