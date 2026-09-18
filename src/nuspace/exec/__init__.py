"""How a Space runs.

Three modules, one per noun. :mod:`nuspace.exec.space` decides which Planes
are up, :mod:`nuspace.exec.plane` decides where a Plane's Cells go, and
:mod:`nuspace.exec.cell` is one Cell executing. All of it runs in the main
process and none of it hosts a Cell: every Cell is in a pool worker, and the
two ``exec_mode`` values differ in how many workers that takes.

:func:`run_space` is the entry: one term, run inside
:func:`nuspace.space.open_space`.
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
from nuspace.exec.space import (
    BOOT_TRIGGERS,
    plane_arm,
    planes_fold,
    run_space,
)
from nuspace.exec.utils import PARK_SECONDS, park, prop, reenters_on


__all__ = [
    "BACKOFF_SECONDS",
    "BACKOFF_STEPS",
    "BOOT_TRIGGERS",
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
    "run_space",
]
