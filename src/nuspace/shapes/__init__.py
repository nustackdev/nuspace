"""The store layout: one entity per file, every op starts from a root here.

Imports ``nu``, ``nustd`` and the specs registry (a content kind's name),
nothing else of nuspace, so everything reads it and it reads nothing back. Two roots, each its own store and tag:
:class:`Space`, what the space is (``store/space.db``), and :class:`State`,
what programs keep (``store/state.db``). Only ids cross between them::

    Space
      info               format, path, created_at, opened_at
      planes[id]         Plane: name, key, icon, parent, version, cells, children,
                         system, backend, spec, meta, created/modified/removed_at, removed_by
      cells[id]          Cell: name, key, prog, fabrics, version, plane, spec, meta, ...
      indexes            spec_planes[s].ids, spec_cells[s].ids, plane_keys, cell_keys, removed
      exec               plane_runs, cell_runs, workers, indexes.history, indexes.live

    State
      cells[id], planes[id], space                    program slots, by scope
      content_cells[kind].cells[id].entries[key]      content, kind first
      content_planes[kind].planes[id].entries[key]
      content_space[kind].entries[key]

A dict's value is a Shape, so each dynamic level that holds a container has
a named slot (``ids``, ``runs``, ``cells``, ``planes``, ``entries``). Places
and ops hide them from programs. Each collection has the view that fits how
it is read: dicts for point reads, FractionalIndexed for a plane's cells and
children, logs for append only lists, dicts of bool for live sets, a ring
for a cell run's output.

Each store is a :class:`Store` record (root, file, channel, init), declared
by the host for the core stores. The web device keeps its own stores and
shapes, in :mod:`nuspace.web.shapes`. Core never reads them.
"""

from .cell import Cell
from .cell_run import OUT_CAP, CellRun
from .content import Content
from .exec import (
    EXIT_FAILED,
    EXIT_INTERRUPTED,
    EXIT_KILLED,
    EXIT_OK,
    EXITS,
    CellRunIds,
    Exec,
    ExecIndexes,
    History,
    Live,
    LiveIds,
    PlaneRunNode,
    PlaneRuns,
)
from .plane import ROOT, Plane
from .plane_run import PlaneRun
from .space import FORMAT, Indexes, Info, Space, SpecIds
from .state import (
    CellScope,
    Entries,
    Entry,
    KindCells,
    KindPlanes,
    PlaneScope,
    SpaceScope,
    State,
)
from .store import Store
from .worker import Worker


__all__ = [
    "EXITS",
    "EXIT_FAILED",
    "EXIT_INTERRUPTED",
    "EXIT_KILLED",
    "EXIT_OK",
    "FORMAT",
    "OUT_CAP",
    "ROOT",
    "Cell",
    "CellRun",
    "CellRunIds",
    "CellScope",
    "Content",
    "Entries",
    "Entry",
    "Exec",
    "ExecIndexes",
    "History",
    "Indexes",
    "Info",
    "KindCells",
    "KindPlanes",
    "Live",
    "LiveIds",
    "Plane",
    "PlaneRun",
    "PlaneRunNode",
    "PlaneRuns",
    "PlaneScope",
    "Space",
    "SpaceScope",
    "SpecIds",
    "State",
    "Store",
    "Worker",
]
