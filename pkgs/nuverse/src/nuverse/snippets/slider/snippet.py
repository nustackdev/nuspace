"""A slider cell: one number in its own state, dragged in place, synced both ways.

Its label is the cell's name, and its range and step are kept next to the
value. Both are edited under Config, and every one of them is live: a change
from any tab, or an op, shows everywhere.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["Level", "out"]


class Level(nuspace.CellState):
    """A slider cell's state: the number, and the range and step it moves within."""

    value = nustd.kv.FloatRef.slot()
    min = nustd.kv.FloatRef.slot()
    max = nustd.kv.FloatRef.slot()
    step = nustd.kv.FloatRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.SliderRef.slot()


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
    """The slider and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")
    low, high, step = Level.min.fallback(0.0), Level.max.fallback(100.0), Level.step.fallback(1.0)

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    def show_min() -> nu.Nu:
        return entry.input.set_min(low) >> settings.min.set_value(low)

    def show_max() -> nu.Nu:
        return entry.input.set_max(high) >> settings.max.set_value(high)

    def show_step() -> nu.Nu:
        return entry.input.set_step(step) >> settings.step.set_value(step)

    return ops.bracketed(
        show_min()
        >> show_max()
        >> show_step()
        >> entry.input.set_value(Level.value.fallback(0.0))
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), Level.value.set(nu.ToFloat(entry.input))),
            nu.ReactForever(settings.min.on_change(), Level.min.set(nu.ToFloat(settings.min))),
            nu.ReactForever(settings.max.on_change(), Level.max.set(nu.ToFloat(settings.max))),
            nu.ReactForever(settings.step.on_change(), Level.step.set(nu.ToFloat(settings.step))),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(Level.value.on_change(), entry.input.set_value(Level.value)),
            nu.ReactForever(Level.min.on_change(), show_min()),
            nu.ReactForever(Level.max.on_change(), show_max()),
            nu.ReactForever(Level.step.on_change(), show_step()),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
