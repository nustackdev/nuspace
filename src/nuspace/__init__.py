"""nuspace: a Nu orchestrator that supports different mediums and behaviors.

Everything is inside a **Space**. A Space is a collection of **Planes**, and a
Plane says how and when its **Cells** run and how they are drawn. A Cell is a
Nu program, and it is the only thing here that executes.

Four modules, and the names are the model::

    nuspace.shapes    the store layout
    nuspace.space     opening a Space in a process
    nuspace.ops       what a person does to a Space
    nuspace.exec      how a Space runs

The store layout and the two entry points are re-exported here, so a program
that lives in a Cell says ``from nuspace import Space`` and a process that
opens one says ``open_space(run_space())``. Everything else is reached through
the module it lives in, because ``ops`` and ``exec`` are families rather than
functions.
"""

from nuspace import exec, ops
from nuspace.exec import run_space
from nuspace.shapes import (
    DEFAULT_EXEC_MODE,
    DEFAULT_RELOAD,
    DEFAULT_RESTART,
    DEFAULT_TRIGGER,
    DEFAULT_VIEWER,
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
    VIEWER_AGENT,
    VIEWER_CODE,
    VIEWER_HEADLESS,
    VIEWER_PROSE,
    VIEWERS,
    Cell,
    CellProps,
    Plane,
    PlaneProps,
    Space,
)
from nuspace.space import open_space, store


__all__ = [
    "DEFAULT_EXEC_MODE",
    "DEFAULT_RELOAD",
    "DEFAULT_RESTART",
    "DEFAULT_TRIGGER",
    "DEFAULT_VIEWER",
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
    "VIEWERS",
    "VIEWER_AGENT",
    "VIEWER_CODE",
    "VIEWER_HEADLESS",
    "VIEWER_PROSE",
    "Cell",
    "CellProps",
    "Plane",
    "PlaneProps",
    "Space",
    "exec",
    "open_space",
    "ops",
    "run_space",
    "store",
]
