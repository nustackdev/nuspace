"""A switch cell: one on or off in its own state, flipped in place, synced both ways.

Its label is the cell's name, edited under Config. Live: a change from any
tab, or an op, shows everywhere.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops


__all__ = ["Flag", "out"]


class Flag(nuspace.CellState):
    """A switch cell's state: whether it is on."""

    value = nustd.kv.BoolRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.SwitchRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "config", "label": "Config"}])


def out() -> nu.Nu:
    """The switch and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    return ops.bracketed(
        entry.input.set(Flag.value.fallback(False))
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), Flag.value.set(nu.ToBool(entry.input))),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(Flag.value.on_change(), entry.input.set(Flag.value)),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
