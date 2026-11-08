"""Execution: ``Space.exec``, the run records and the indexes that relate them.

Like an executable and its processes: a plane or a cell is the program, its
runs are processes, any number of them, several at once::

    Space.exec
      plane_runs    id -> PlaneRun
      cell_runs     id -> CellRun
      workers       id -> Worker
      indexes
        history                                   every run ever, never cleared
          plane_to_plane_runs[p].runs             a plane's runs, in start order
            [r].cell_to_cell_runs[c].ids          a cell's runs in r, in start order
            [r].workers                           r's workers
        live                                      what runs now, cleared at open
          plane_runs                              every live plane run
          plane_to_plane_runs[p].ids              a plane's live runs
          cell_to_cell_runs[c].ids                a cell's live runs, any plane run
          plane_run_to_cell_runs[r].ids           r's live cell runs
          plane_run_to_failed_cells[r].ids        cells whose last cell run in r failed
          plane_run_to_workers[r].ids             r's held workers
          workers                                 every live worker

Records hold their own facts plus a back ref. Every list is an index here,
written in the same commit as the record change it mirrors. A dict's value
is a Shape, so each dynamic level that holds a list gets a named slot
(``runs``, ``ids``).

Views: records and keyed levels are plain dicts (point reads). History
lists are logs: append only, read a page at a time, newest first. Live sets
are dicts of bool: point add and delete, ``nu.Not(set)`` for empty, and no
count key shared by every writer.

Nothing here is iterated whole. Live questions read ``live``, history
questions one plane's or one plane run's list.
"""

from __future__ import annotations

import nu
import nustd.kv

from .cell_run import CellRun
from .plane_run import PlaneRun
from .worker import Worker


__all__ = [
    "EXITS",
    "EXIT_FAILED",
    "EXIT_INTERRUPTED",
    "EXIT_KILLED",
    "EXIT_OK",
    "CellRunIds",
    "Exec",
    "ExecIndexes",
    "History",
    "Live",
    "LiveIds",
    "PlaneRunNode",
    "PlaneRuns",
]


#: It returned. For a plane run, no cell's last run in it failed. For a
#: worker, its backend let it go once the plane run was over.
EXIT_OK = "ok"

#: It raised, or its worker died under it. For a worker, it died by itself.
EXIT_FAILED = "failed"

#: Somebody asked: an interrupt, or a removed cell or plane.
EXIT_INTERRUPTED = "interrupted"

#: Torn down: kill_at passed, or reap found it left over at open.
EXIT_KILLED = "killed"

#: How a run or a worker ended. Tells a crash from a request.
EXITS = (EXIT_OK, EXIT_FAILED, EXIT_INTERRUPTED, EXIT_KILLED)


class CellRunIds(nu.Shape):
    """One cell's runs inside one plane run, in start order: ``...cell_to_cell_runs[c]``."""

    ids = nustd.kv.LogDictRef.slot(bool)


class PlaneRunNode(nu.Shape):
    """One plane run's node in history: ``...plane_to_plane_runs[p].runs[r]``.

    ``cell_to_cell_runs`` maps a cell to its runs in this plane run,
    ``workers`` lists the workers the run ever held. Reaching a node needs
    its plane: one read of ``PlaneRun.plane``.
    """

    cell_to_cell_runs = nustd.kv.DictRef.slot(CellRunIds)
    workers = nustd.kv.LogDictRef.slot(bool)


class PlaneRuns(nu.Shape):
    """One plane's runs, in start order: ``history.plane_to_plane_runs[p]``."""

    runs = nustd.kv.LogDictRef.slot(PlaneRunNode)


class History(nu.Shape):
    """Every run ever, by plane. Never cleared; nothing walks it whole."""

    plane_to_plane_runs = nustd.kv.DictRef.slot(PlaneRuns)


class LiveIds(nu.Shape):
    """One keyed live set: ``live.<set>[x].ids``, the ids of what is live for ``x``."""

    ids = nustd.kv.DictRef.slot(bool)


class Live(nu.Shape):
    """What runs now. Cleared at open, after reap has ended the leftovers as killed.

    ``plane_runs`` is what the kernel folds over. The keyed sets answer one
    question each in one read: a plane's live runs, a cell's live runs, a
    plane run's live cell runs (empty: the plane run is done), the cells
    whose last cell run in a plane run failed (not empty: the plane run
    failed), a plane run's held workers. ``workers`` is every live worker,
    what reap walks at open.
    """

    plane_runs = nustd.kv.DictRef.slot(bool)
    plane_to_plane_runs = nustd.kv.DictRef.slot(LiveIds)
    cell_to_cell_runs = nustd.kv.DictRef.slot(LiveIds)
    plane_run_to_cell_runs = nustd.kv.DictRef.slot(LiveIds)
    plane_run_to_failed_cells = nustd.kv.DictRef.slot(LiveIds)
    plane_run_to_workers = nustd.kv.DictRef.slot(LiveIds)
    workers = nustd.kv.DictRef.slot(bool)


class ExecIndexes(nu.Shape):
    """How the records relate (``history``) and what is running now (``live``)."""

    history = nustd.kv.ShapeRef.slot(History)
    live = nustd.kv.ShapeRef.slot(Live)


class Exec(nu.Shape):
    """``Space.exec``: every plane run, cell run and worker ever, by id, and their indexes."""

    plane_runs = nustd.kv.DictRef.slot(PlaneRun)
    cell_runs = nustd.kv.DictRef.slot(CellRun)
    workers = nustd.kv.DictRef.slot(Worker)
    indexes = nustd.kv.ShapeRef.slot(ExecIndexes)
