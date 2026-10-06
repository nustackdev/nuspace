"""Layer one: the ops, nuspace's language.

Every op is a function returning a Nu term. Planes' cells, services, the
agent and the shell compose these and nothing narrower.

- **Writes are one commit each.** An op brackets itself in a kv transaction
  over :class:`~nuspace.shapes.Space`, retried on conflict, so nothing reads
  half of it and it is safe from any process holding the store, a proxied
  navigator on a worker included. Nothing brackets a term for its author:
  ops, services and cell programs all keep the one bracket rule in
  :mod:`nuspace.ops.utils`, by hand with :func:`atomic`, :func:`atomic_state`
  and :func:`snapshot`, or with :func:`bracketed` around a whole program.
- **Queries yield, effects write.** A query, a pure read or computation,
  evaluates to its value. A flow or an op with effects never hands a
  result back: it writes what it made or decided into a ref, yields
  nothing, and chains with ``>>``; whoever needs the result reads that
  ref. Mostly the ref is the record itself: a plane made is listed under its parent,
  a plane moved has its new parent. Where the record cannot say which one
  this call made, the op takes an ``into`` ref, a mem ref the caller holds
  or a kv ref in the store it commits to, and sets it as part of its
  writes.
- **Ids are minted at evaluation.** A term is built once and may run many
  times (eg in an arm), so an op that makes something mints its id when it
  runs.
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
    cell_plane,
    cell_rows,
    cells,
    children,
    parent,
    plane_exists,
    plane_rows,
    plane_title,
    planes,
    prog,
)
from .settings import set_telemetry, telemetry
from .state import (
    CellState,
    PlaneState,
    bracketed,
    cell_state,
    clear_cell_state,
    clear_plane_state,
    plane_state,
    sibling,
)
from .tree import move_plane
from .utils import atomic, atomic_state, mint_ordered_id, snapshot


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
    "atomic",
    "atomic_state",
    "bracketed",
    "cell_exists",
    "cell_interrupt",
    "cell_plane",
    "cell_rows",
    "cell_run",
    "cell_runs",
    "cell_state",
    "cells",
    "children",
    "clear_cell_state",
    "clear_plane_state",
    "create_plane",
    "env",
    "insert_snippet",
    "latest",
    "mint_ordered_id",
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
    "plane_title",
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
