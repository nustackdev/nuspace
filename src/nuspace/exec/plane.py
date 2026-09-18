"""Where a Plane's Cells go, per ``exec_mode``.

A Plane is arrangement. Nothing evaluates a Plane, so running one means
starting its Cells the way its props say, and the only question this module
answers is which process each Cell lands in.

Both modes offload and they differ in granularity, which comes out as where
the fold over the Cells sits:

- ``async`` ships the fold into one worker. The Cells are asyncio tasks in
  that process, the worker reads its own Cell list through the proxied
  Navigator and hears the change feed, so a Cell added or edited is a task
  starting or reloading inside a process that is already up.
- ``mp`` keeps the fold here and each arm dispatches a worker of its own. A
  Cell gets a process nothing else is in, and pays an interpreter for it.

So these are two shapes rather than one with a flag on it. What they have in
common is the Cell arm, which is the same term either way.
"""

from __future__ import annotations

import nu
import nustd.kv
import nustd.mp_pool
from nuspace.exec.cell import CELL_ATTR, cell_arm, cell_dispatch
from nuspace.exec.utils import park, prop
from nuspace.shapes import DEFAULT_EXEC_MODE, EXEC_ASYNC, EXEC_MP, Space


__all__ = [
    "PLANE_ATTR",
    "async_plane",
    "cells_fold",
    "mp_plane",
    "run_plane",
]


#: What a Plane fold binds each Plane id under. Carried into a worker as it
#: stands, so a term built here reads the same name there.
PLANE_ATTR = "plane"

#: The pool worker holding an ``async`` Plane, while it is up.
_WORKER_ATTR = "nuspace.plane.worker"


def cells_fold(plane: nu.StrArg, arm: nu.Nu, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """One live ``arm`` per Cell in the Plane, births and deaths included.

    The subscription is length exact: it fires when a Cell is added or
    removed and never when one is edited, which is exactly when the set of
    arms changed. Editing a Cell is the arm's own business.

    Args:
        plane: the Plane whose Cells these are.
        arm: what one Cell runs. Spawned when the Cell appears, cancelled and
            drained when it goes.
        root: the Space shape class the Plane is stored under.
    """
    cells = root.planes[plane].cells
    # nu.list is load bearing: a keys view is lazy and the atomicity pass
    # brackets the items slot separately, so an undrained view outlives its
    # snapshot and dies reading closed storage.
    return nu.ForEachParReactive(
        nu.list(cells.keys()),
        cells.on_children_change(),
        arm,
        CELL_ATTR,
    )


def _cells_exist(plane: nu.StrArg, *, root: type[nu.Shape]) -> nu.Nu:
    """Make the Cell container real before anything subscribes to it.

    A subscription over a container that is not there resolves to INVALID and
    silently never fires, and a fold handed one raises instead, which an
    enclosing fold would isolate and spawn again forever. Written here rather
    than wherever the fold ends up, because ``Dict.create()`` does not survive
    the pickle into a worker.
    """
    return root.planes[plane].cells.init(nu.Dict.create())


def async_plane(plane: nu.StrArg, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """The whole Plane in one worker, its Cells as tasks in that process.

    The fold is built here and run there. It reads its own Cell list rather
    than being handed one that goes stale between the dispatch and the run,
    and the Plane id reaches it as a carried attr. The worker is killed on
    every way out of this branch, the Plane being stopped included.

    The body is bracketed for atomicity before the ``Dispatch`` is built,
    because a dispatched body is payload and no pass reaches it.

    Args:
        plane: the Plane to run.
        root: the Space shape class the Plane is stored under.
    """
    pool = nustd.mp_pool.PoolRef()
    worker = nu.IntAttrRef(_WORKER_ATTR)
    body = nustd.kv.auto_flow_atomic(
        cells_fold(plane, cell_arm(plane, root=root), root=root), scope=root
    )
    return _cells_exist(plane, root=root) >> nu.Let(
        _WORKER_ATTR,
        pool.launch(),
        # Dispatch returns as soon as the child has the body, so the park is
        # what holds the worker open.
        body=nu.TryCatch(
            pool.dispatch(body, worker, carry=True) >> park(),
            finally_=pool.kill(worker),
        ),
    )


def mp_plane(plane: nu.StrArg, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """A worker per Cell, the fold staying in this process.

    Nothing user written runs here either: each arm launches a process and
    ships the Cell into it. What stays is the reconciling, which is the whole
    reason this mode costs what it costs.

    Args:
        plane: the Plane to run.
        root: the Space shape class the Plane is stored under.
    """
    return _cells_exist(plane, root=root) >> cells_fold(
        plane, cell_dispatch(plane, root=root), root=root
    )


def run_plane(plane: nu.StrArg, *, root: type[nu.Shape] = Space) -> nu.Nu:
    """This Plane's Cells, put where its ``exec_mode`` says.

    Total on purpose: a Plane whose ``exec_mode`` is unwritten or is a word
    nuspace does not know runs the default arrangement rather than nothing,
    because a Plane that silently does not start is the worst of the three
    answers.

    Args:
        plane: the Plane to run.
        root: the Space shape class the Plane is stored under.
    """
    modes = {EXEC_ASYNC: async_plane, EXEC_MP: mp_plane}
    return nu.SwitchDo(
        prop(root.planes[plane].props.exec_mode, DEFAULT_EXEC_MODE),
        {mode: build(plane, root=root) for mode, build in modes.items()},
        modes[DEFAULT_EXEC_MODE](plane, root=root),
    )
