"""The store layout: layer zero.

Imports ``nu`` and ``nustd.kv`` and nothing of nuspace, so everything above
reads it and it reads nothing back::

    Space
      planes        id -> Plane
        <p>
          name, system, meta
          state     PlaneState shapes, rerooted here
          cells     id -> Cell
            <c>
              name, prog, meta
              state CellState shapes, rerooted here
          order     [cell id]
      tree          id -> Node (children), ROOT at the top
      kernel
        workers     id -> Worker
        runs        id -> Run
        live        run id -> worker id
        active      worker id -> True
      connections   id -> Connection

Plane and cell hold structure only. How and when a cell runs is the caller's
argument, and what it did is a run.
"""

from .cell import Cell
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
from .plane import Plane
from .reroot import Reroot, reroot, reroot_base
from .space import Space
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
    "ROOT",
    "STATUSES",
    "STATUS_DEAD",
    "STATUS_STARTING",
    "STATUS_STOPPING",
    "STATUS_UP",
    "Cell",
    "CellState",
    "Connection",
    "Kernel",
    "Node",
    "Plane",
    "PlaneState",
    "Reroot",
    "Run",
    "Space",
    "Worker",
    "reroot",
    "reroot_base",
]
