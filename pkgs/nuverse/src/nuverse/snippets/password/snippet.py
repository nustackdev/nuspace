"""A password generator: a length, three switches, and a fresh password whenever one changes.

The options and the password live in the cell's state, so the last password
is still there when the plane opens again. Drawn with :mod:`secrets`, not
:mod:`random`: it is meant to be used.
"""

from __future__ import annotations

import secrets
import string

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["Pass", "out"]


def _draw(alphabet: str, length: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(int(length)))


#: ``length`` characters drawn from ``alphabet``, each from the OS's secure source.
Draw = nu.host(_draw, name="PasswordDraw")


class Pass(nuspace.CellState):
    """The generator's state: its options, and the password they made last."""

    length = nustd.kv.IntRef.slot()
    upper = nustd.kv.BoolRef.slot()
    digits = nustd.kv.BoolRef.slot()
    symbols = nustd.kv.BoolRef.slot()
    password = nustd.kv.StrRef.slot()


class Options(nustd.ui.Row):
    upper = nustd.ui.SwitchRef.slot(label="A-Z")
    digits = nustd.ui.SwitchRef.slot(label="0-9")
    symbols = nustd.ui.SwitchRef.slot(label="!@#")
    generate = nustd.ui.ButtonRef.slot(label="Generate", variant="secondary")


class Box(nustd.ui.Column):
    password = nustd.ui.CodeRef.slot()
    length = nustd.ui.SliderRef.slot(label="Length", min=8, max=64)
    options = Options.slot(gap=4, wrap=True)


def out() -> nu.Nu:
    """The generator, for as long as the cell runs: an option changed, or Generate, draws again."""
    length = Pass.length.fallback(20)
    upper, digits, symbols = (s.fallback(True) for s in (Pass.upper, Pass.digits, Pass.symbols))
    alphabet = (
        nu.Str(string.ascii_lowercase)
        + nu.If(upper, string.ascii_uppercase, "")
        + nu.If(digits, string.digits, "")
        + nu.If(symbols, "!@#$%^&*-_=+?", "")
    )
    draw = Pass.password.set(Draw(alphabet, length))

    def keep(slot: nu.Nu, value: nu.Nu) -> nu.Nu:
        # The option first, then a password made with it, in one commit.
        return slot.set(value) >> draw

    first = nu.IfDo(Pass.password.missing(), draw)
    return ops.bracketed(
        first
        >> Box.password.set(nu.str(Pass.password))
        >> Box.length.set_value(length)
        >> Box.options.upper.set(upper)
        >> Box.options.digits.set(digits)
        >> Box.options.symbols.set(symbols)
        >> nu.ParallelAsync(
            nu.ReactForever(Box.options.generate.on_click(), draw),
            nu.ReactForever(Box.length.on_change(), keep(Pass.length, nu.ToInt(Box.length))),
            nu.ReactForever(
                Box.options.upper.on_change(), keep(Pass.upper, nu.ToBool(Box.options.upper))
            ),
            nu.ReactForever(
                Box.options.digits.on_change(), keep(Pass.digits, nu.ToBool(Box.options.digits))
            ),
            nu.ReactForever(
                Box.options.symbols.on_change(), keep(Pass.symbols, nu.ToBool(Box.options.symbols))
            ),
            # Every tab shows the password the store holds.
            nu.ReactForever(Pass.password.on_change(), Box.password.set(nu.str(Pass.password))),
        )
    )
