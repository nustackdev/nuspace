"""The store layout: layer zero.

Imports ``nu`` and ``nustd.kv`` and nothing of nuspace, so everything above
reads it and it reads nothing back::

    Space
      planes        id -> Plane
        <p>
          name, meta
          props     system, ui, made_by, backend
          state     PlaneState shapes, rerooted here
          cells     id -> Cell
            <c>
              name, prog, version, meta
              props made_by
              state CellState shapes, rerooted here
          order     [cell id]
      tree          id -> Node (children), ROOT at the top
      kernel
        runs        id -> Run, every plane run ever, its cell runs inside
        running     {run id}, live
        workers     id -> Worker, every worker ever
        workers_running  {worker id}, live
      connections   id -> Connection
      state         SpaceState
        recents     [plane id], newest first
        info        path, opened, versions
      settings      SpaceSettings
        telemetry   bool, off when unset
      pinned        [plane id], in order

Plane and cell hold structure only, but for the plane's ``backend``. What
ran and how it ended is a run.
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
    Run,
    Worker,
)
from .plane import DEFAULT_BACKEND, Plane, PlaneProps
from .reroot import Reroot, reroot, reroot_base
from .space import RECENTS_CAP, Space, SpaceInfo, SpaceSettings, SpaceState
from .state import CellState, PlaneState
from .tree import ROOT, Node


__all__ = [
    "DEFAULT_BACKEND",
    "EXITS",
    "EXIT_FAILED",
    "EXIT_INTERRUPTED",
    "EXIT_KILLED",
    "EXIT_OK",
    "RECENTS_CAP",
    "ROOT",
    "Cell",
    "CellProps",
    "CellRun",
    "CellState",
    "Connection",
    "Kernel",
    "Node",
    "Plane",
    "PlaneProps",
    "PlaneState",
    "Reroot",
    "Run",
    "Space",
    "SpaceInfo",
    "SpaceSettings",
    "SpaceState",
    "Worker",
    "reroot",
    "reroot_base",
]
