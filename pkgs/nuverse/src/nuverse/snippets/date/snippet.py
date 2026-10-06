"""A date cell: one date in its own state, picked in place, synced both ways.

Its label is the cell's name, edited under Config. Live: a change from any
tab, or an op, shows everywhere. Cleared, the date is gone.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.datetime.kv
import nustd.ui
from nuspace import ops


__all__ = ["Day", "out"]


class Day(nuspace.CellState):
    """A date cell's state: the date, missing until one is picked."""

    value = nustd.datetime.kv.DateRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.DatePickerRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "config", "label": "Config"}])


def _iso() -> nu.Nu:
    """The date as the picker takes it: ISO, ``""`` for none."""
    return nu.If(Day.value.exists(), nu.ToStr(Day.value), "")


def _keep(picked: nu.Nu) -> nu.Nu:
    """What the picker holds stored: cleared, the date is gone."""
    iso = nu.Str(picked)
    return nu.IfDo(iso == "", Day.value.erase(), Day.value.set(iso))


def out() -> nu.Nu:
    """The date and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    return ops.bracketed(
        entry.input.set(_iso())
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), _keep(entry.input)),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(Day.value.on_change(), entry.input.set(_iso())),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
