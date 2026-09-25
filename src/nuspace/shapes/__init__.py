"""The store layout: layer zero.

Imports ``nu`` and ``nustd.kv`` and nothing of nuspace, so everything above
reads it and it reads nothing back::

    Space
      planes        id -> Plane
        <p>
          name, meta
          props     system, ui, made_by
          state     PlaneState shapes, rerooted here
          cells     id -> Cell
            <c>
              name, prog, meta
              props made_by
              state CellState shapes, rerooted here
          order     [cell id]
      tree          id -> Node (children), ROOT at the top
      kernel
        workers     id -> Worker
        runs        id -> Run
        live        run id -> worker id
        active      worker id -> True
      connections   id -> Connection
      state         SpaceState
        recents     [plane id], newest first
        info        path, opened, versions
      settings      SpaceSettings
        telemetry   bool, off when unset
      pinned        [plane id], in order

Plane and cell hold structure only. How and when a cell runs is the caller's
argument, and what it did is a run.
"""

from .cell import Cell, CellProps
from .connection import Connection
from .kernel import (
    EXIT_FAILED,
    EXIT_KILLED,
    EXIT_OK,
    EXIT_STOPPED,
    EXITS,
    KIND_DOCKER,
    KIND_LOCAL,
    KIND_REMOTE,
    KINDS,
    STATUS_DEAD,
    STATUS_STARTING,
    STATUS_STOPPING,
    STATUS_UP,
    STATUSES,
    Kernel,
    Run,
    Worker,
)
from .plane import Plane, PlaneProps
from .reroot import Reroot, reroot, reroot_base
from .space import RECENTS_CAP, Space, SpaceInfo, SpaceSettings, SpaceState
from .state import CellState, PlaneState
from .tree import ROOT, Node


__all__ = [
    "EXITS",
    "EXIT_FAILED",
    "EXIT_KILLED",
    "EXIT_OK",
    "EXIT_STOPPED",
    "KINDS",
    "KIND_DOCKER",
    "KIND_LOCAL",
    "KIND_REMOTE",
    "RECENTS_CAP",
    "ROOT",
    "STATUSES",
    "STATUS_DEAD",
    "STATUS_STARTING",
    "STATUS_STOPPING",
    "STATUS_UP",
    "Cell",
    "CellProps",
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
