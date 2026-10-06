"""The store layout: layer zero.

Imports ``nu`` and ``nustd.kv`` and nothing of nuspace, so everything above
reads it and it reads nothing back. Two stores, each its own root and tag.
Space, what the space is::

    Space
      planes        id -> Plane
        <p>
          name, meta
          props     system, ui, made_by, backend
          cells     [cell id], in order
          children  [plane id], in order
          parent    plane id, "" at the top level
          version   +1 on every write to one of its cells
      cells         id -> Cell
        <c>
          name, prog, version, meta
          props     made_by, has_ui
          plane     the plane it is on
      top           [plane id], the top level planes, in order
      kernel
        runs        id -> Run, every plane run ever, its cell runs and live workers inside
        running     {run id}, live
        workers     id -> Worker, every worker ever
        workers_running  {worker id}, live
        planes_running   plane id -> {run id}, live, of planes with any
      connections   id -> Connection
      state         SpaceState
        recents     [plane id], newest first
        info        path, opened, versions
      settings      SpaceSettings
        telemetry   bool, off when unset
      pinned        [plane id], in order

States, what the programs remember, by the same ids::

    States
      planes        id -> PlaneStates
        <p>
          state     PlaneState shapes, rerooted here
      cells         id -> CellStates
        <c>         CellState shapes, rerooted here

Plane and cell hold structure only, but for the plane's ``backend``. What
ran and how it ended is a run. What a program remembers is a state.
"""

from .cell import Cell, CellProps
from .connection import Connection
from .kernel import (
    EXIT_FAILED,
    EXIT_INTERRUPTED,
    EXIT_KILLED,
    EXIT_OK,
    EXITS,
    CellRun,
    Kernel,
    PlaneRuns,
    Run,
    Worker,
)
from .plane import Plane, PlaneProps
from .reroot import Reroot, reroot, reroot_base
from .space import RECENTS_CAP, Space, SpaceInfo, SpaceSettings, SpaceState
from .state import CellState, PlaneState
from .states import CellStates, PlaneStates, States


__all__ = [
    "EXITS",
    "EXIT_FAILED",
    "EXIT_INTERRUPTED",
    "EXIT_KILLED",
    "EXIT_OK",
    "RECENTS_CAP",
    "Cell",
    "CellProps",
    "CellRun",
    "CellState",
    "CellStates",
    "Connection",
    "Kernel",
    "Plane",
    "PlaneProps",
    "PlaneRuns",
    "PlaneState",
    "PlaneStates",
    "Reroot",
    "Run",
    "Space",
    "SpaceInfo",
    "SpaceSettings",
    "SpaceState",
    "States",
    "Worker",
    "reroot",
    "reroot_base",
]
