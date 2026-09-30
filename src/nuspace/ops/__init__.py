"""Layer one: the ops, nuspace's language.

Every op is a function returning a Nu term. Planes' cells, services, the
agent and the shell compose these and nothing narrower.

- **Writes are one commit each.** An op brackets itself in a kv transaction
  over :class:`~nuspace.shapes.Space`, retried on conflict, so nothing reads
  half of it and it is safe from any process holding the store, a proxied
  navigator on a worker included.
- **Ids are minted at evaluation.** A term is built once and may run many
  times (eg in an arm), so an op that makes something mints its id when it
  runs and yields it. Yielding ops are Actions: they chain with ``>>`` and
  bind with ``nu.Let``.
- **Reads are bare.** They compose into any expression and read inside the
  enclosing bracket. Alone, wrap one in ``nustd.kv.Snapshot(..., scope=Space)``,
  or in :func:`snapshot` when it reads program state too.
- **Two stores.** Space holds structure, runs and devices; States holds
  program state, by plane and cell id. A write op commits to one; one that
  touches both is a commit to each, Space first (see
  :func:`~.utils.atomic_state`).
- **Kernel ops write intents only.** The kernel and the backends, in the
  host, make them true and write the effects (see :mod:`nuspace.ops.kernel`).
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
from .extend import TEXT, Plane, Snippet, create_plane, insert_snippet
from .kernel import (
    STOP_GRACE,
    Here,
    cell_interrupt,
    cell_run,
    cell_runs,
    env,
    latest,
    plane_interrupt,
    plane_kill,
    plane_run,
    plane_stop,
    run,
    runs,
    workers,
)
from .pin import move_pin, pin_plane, pinned, unpin_plane
from .plane import add_plane, remove_plane, rename_plane, set_plane_icon, set_plane_meta
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
from .settings import set_telemetry, telemetry
from .state import CellState, PlaneState, cell_state, clear_state, plane_state, sibling
from .tree import move_plane
from .utils import mint_ordered_id, snapshot


__all__ = [
    "STOP_GRACE",
    "TEXT",
    "CellState",
    "Here",
    "Plane",
    "PlaneState",
    "Snippet",
    "add_cell",
    "add_plane",
    "cell_exists",
    "cell_interrupt",
    "cell_rows",
    "cell_run",
    "cell_runs",
    "cell_state",
    "cells",
    "children",
    "clear_state",
    "create_plane",
    "env",
    "insert_snippet",
    "latest",
    "mint_ordered_id",
    "move_cell",
    "move_pin",
    "move_plane",
    "parent",
    "pin_plane",
    "pinned",
    "plane_exists",
    "plane_interrupt",
    "plane_kill",
    "plane_rows",
    "plane_run",
    "plane_state",
    "plane_stop",
    "planes",
    "prog",
    "remove_cell",
    "remove_plane",
    "rename_cell",
    "rename_plane",
    "reorder_cells",
    "run",
    "runs",
    "set_cell_meta",
    "set_plane_icon",
    "set_plane_meta",
    "set_prog",
    "set_telemetry",
    "sibling",
    "snapshot",
    "telemetry",
    "unpin_plane",
    "workers",
]
