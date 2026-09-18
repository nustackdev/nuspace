"""How a Space runs.

Three modules, one per noun. :mod:`nuspace.exec.space` folds the Planes in a
Space, :mod:`nuspace.exec.plane` places a Plane's Cells, and
:mod:`nuspace.exec.cell` is one Cell executing. None of it hosts a Cell:
every Cell is in a pool worker, and the two ``exec_mode`` values differ in
how many workers that takes.

Combinators, all of it. Which Planes are up and what a Cell draws on are both
arguments here and decisions in :mod:`nuspace.drivers`, which is what keeps
the runtime language from knowing what a viewer is.
"""

from nuspace.exec.cell import (
    BACKOFF_SECONDS,
    BACKOFF_STEPS,
    CELL_ATTR,
    cell_arm,
    cell_body,
    cell_dispatch,
)
from nuspace.exec.plane import (
    PLANE_ATTR,
    async_plane,
    cells_fold,
    mp_plane,
    run_plane,
)
from nuspace.exec.space import plane_arm, planes_fold
from nuspace.exec.utils import PARK_SECONDS, park, prop, reenters_on


__all__ = [
    "BACKOFF_SECONDS",
    "BACKOFF_STEPS",
    "CELL_ATTR",
    "PARK_SECONDS",
    "PLANE_ATTR",
    "async_plane",
    "cell_arm",
    "cell_body",
    "cell_dispatch",
    "cells_fold",
    "mp_plane",
    "park",
    "plane_arm",
    "planes_fold",
    "prop",
    "reenters_on",
    "run_plane",
]
