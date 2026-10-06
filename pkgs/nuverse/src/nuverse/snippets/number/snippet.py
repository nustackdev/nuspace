"""A number cell: one number in its own state, edited in place, synced both ways.

Its label is the cell's name, and its bounds (0 to 100 until set) and step
are kept next to the value. Both are edited under Config, and every one of them is live: a change
from any tab, or an op, shows everywhere.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["Number", "out"]


class Number(nuspace.CellState):
    """A number cell's state: the number, and the bounds and step it is edited within."""

    value = nustd.kv.FloatRef.slot()
    min = nustd.kv.FloatRef.slot()
    max = nustd.kv.FloatRef.slot()
    step = nustd.kv.FloatRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.NumberInputRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")
    min = nustd.ui.NumberInputRef.slot(label="Min")
    max = nustd.ui.NumberInputRef.slot(label="Max", default=100)
    step = nustd.ui.NumberInputRef.slot(label="Step", min=0, step=0.1, default=1)


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "config", "label": "Config"}])


def out() -> nu.Nu:
    """The number and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")
    low, high, step = (
        Number.min.fallback(0.0),
        Number.max.fallback(100.0),
        Number.step.fallback(1.0),
    )

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    def show_min() -> nu.Nu:
        return entry.input.set_min(low) >> settings.min.set_value(low)

    def show_max() -> nu.Nu:
        return entry.input.set_max(high) >> settings.max.set_value(high)

    def show_step() -> nu.Nu:
        return entry.input.set_step(step) >> settings.step.set_value(step)

    return ops.bracketed(
        entry.input.set_value(Number.value.fallback(0.0))
        >> show_name()
        >> show_min()
        >> show_max()
        >> show_step()
        >> nu.ParallelAsync(
            # This tab edited: keep it. Everyone else hears it through the store.
            nu.ReactForever(entry.input.on_change(), Number.value.set(nu.ToFloat(entry.input))),
            nu.ReactForever(settings.min.on_change(), Number.min.set(nu.ToFloat(settings.min))),
            nu.ReactForever(settings.max.on_change(), Number.max.set(nu.ToFloat(settings.max))),
            nu.ReactForever(settings.step.on_change(), Number.step.set(nu.ToFloat(settings.step))),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            # Somebody else edited, or an op set it: show it.
            nu.ReactForever(Number.value.on_change(), entry.input.set_value(Number.value)),
            nu.ReactForever(Number.min.on_change(), show_min()),
            nu.ReactForever(Number.max.on_change(), show_max()),
            nu.ReactForever(Number.step.on_change(), show_step()),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
