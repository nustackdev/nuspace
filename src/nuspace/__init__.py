"""nuspace: a Nu orchestrator that supports different mediums and behaviors.

Everything is inside a **Space**. A Space is a collection of **Planes**, and a
Plane says how and when its **Cells** run and how they are drawn. A Cell is a
Nu program, and it is the only thing here that executes.

Six modules, and the names are the model::

    nuspace.shapes    the store layout
    nuspace.space     opening a Space in a process
    nuspace.ops       what a person does to a Space
    nuspace.exec      how a Space runs
    nuspace.drivers   when and what runs
    nuspace.presets   a Space open with some set of drivers in it

The store layout and the two entry points are re-exported here, so a program
that lives in a Cell says ``from nuspace import Space`` and a process that
opens one says ``open_space(run_space())``. Everything else is reached through
the module it lives in, because ``ops``, ``exec``, ``drivers`` and ``presets``
are families rather than functions.
"""

from nuspace import drivers, exec, ops, presets
from nuspace.drivers import run_space
from nuspace.shapes import (
    DEFAULT_EDITABLE,
    DEFAULT_EXEC_MODE,
    DEFAULT_RELOAD,
    DEFAULT_RESTART,
    DEFAULT_TRIGGER,
    DEFAULT_UI,
    EXEC_ASYNC,
    EXEC_MODES,
    EXEC_MP,
    RESTART_ALWAYS,
    RESTART_NO,
    RESTART_ON_FAILURE,
    RESTARTS,
    TRIGGER_BOOT,
    TRIGGER_MANUAL,
    TRIGGER_NAV,
    TRIGGERS,
    Cell,
    CellProps,
    Plane,
    PlaneProps,
    Space,
)
from nuspace.space import open_space, store


__all__ = [
    "DEFAULT_EDITABLE",
    "DEFAULT_EXEC_MODE",
    "DEFAULT_RELOAD",
    "DEFAULT_RESTART",
    "DEFAULT_TRIGGER",
    "DEFAULT_UI",
    "EXEC_ASYNC",
    "EXEC_MODES",
    "EXEC_MP",
    "RESTARTS",
    "RESTART_ALWAYS",
    "RESTART_NO",
    "RESTART_ON_FAILURE",
    "TRIGGERS",
    "TRIGGER_BOOT",
    "TRIGGER_MANUAL",
    "TRIGGER_NAV",
    "Cell",
    "CellProps",
    "Plane",
    "PlaneProps",
    "Space",
    "drivers",
    "exec",
    "open_space",
    "ops",
    "presets",
    "run_space",
    "store",
]
