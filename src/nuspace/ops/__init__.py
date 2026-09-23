"""Layer one: the ops, nuspace's language.

Every op is a function returning a Nu term. Apps, services, the agent and
the shell compose these and nothing narrower.

- **Writes are one commit each.** An op brackets itself in a kv transaction
  over :class:`~nuspace.shapes.Space`, retried on conflict, so nothing reads
  half of it and it is safe from any process holding the store, a proxied
  navigator on a worker included.
- **Ids are minted at evaluation.** A term is built once and may run many
  times (eg in an arm), so an op that makes something mints its id when it
  runs and yields it. Yielding ops are Actions: they chain with ``>>`` and
  bind with ``nu.Let``.
- **Reads are bare.** They compose into any expression and read inside the
  enclosing bracket. Alone, wrap one in ``nustd.kv.Snapshot(..., scope=Space)``.
- **Kernel ops write records only.** The kernel, in the host, makes them
  true (see :mod:`nuspace.ops.kernel`).
"""

from .cell import (
    add_cell,
    move_cell,
    remove_cell,
    rename_cell,
    reorder_cells,
    set_cell_meta,
    set_prog,
)
from .extend import App, Snippet, insert_snippet, run_app
from .kernel import (
    CELL_ATTR,
    PLANE_ATTR,
    RUN_ATTR,
    active_workers,
    down,
    env,
    kill_worker,
    live_runs,
    runs,
    up,
    up_plane,
    worker,
    workers,
)
from .plane import add_plane, remove_plane, rename_plane, set_plane_meta
from .read import (
    cell_exists,
    cell_rows,
    cells,
    children,
    parent,
    plane_exists,
    plane_rows,
    planes,
    prog,
)
from .state import CellState, PlaneState, clear_state, sibling
from .tree import nest, unnest
from .utils import mint_ordered_id


__all__ = [
    "CELL_ATTR",
    "PLANE_ATTR",
    "RUN_ATTR",
    "App",
    "CellState",
    "PlaneState",
    "Snippet",
    "active_workers",
    "add_cell",
    "add_plane",
    "cell_exists",
    "cell_rows",
    "cells",
    "children",
    "clear_state",
    "down",
    "env",
    "insert_snippet",
    "kill_worker",
    "live_runs",
    "mint_ordered_id",
    "move_cell",
    "nest",
    "parent",
    "plane_exists",
    "plane_rows",
    "planes",
    "prog",
    "remove_cell",
    "remove_plane",
    "rename_cell",
    "rename_plane",
    "reorder_cells",
    "run_app",
    "runs",
    "set_cell_meta",
    "set_plane_meta",
    "set_prog",
    "sibling",
    "unnest",
    "up",
    "up_plane",
    "worker",
    "workers",
]
