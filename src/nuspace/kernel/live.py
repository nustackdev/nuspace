"""The live indexes' sets: what the kernel folds over, made where missing.

``Space.exec.indexes.live`` lists what is live now: the plane runs asked
for and not ended, their cell runs and workers. The ops write it and the
kernel trusts it, so it is the kernel's to make: the kernel's init
(:func:`~.driver.init`) runs :func:`init_live` in its own commit, after
core's; reap runs it again when it has to clear ``live`` after its ends failed.
"""

from __future__ import annotations

import nu
from nuspace.shapes import Space


__all__ = ["init_live"]


def init_live() -> nu.Nu:
    """``Space.exec.indexes.live``'s sets, made where missing. Bare: the caller brackets it.

    Safe on every open: what is there is left as it is.
    """
    live = Space.exec.indexes.live
    return (
        live.plane_runs.init(nu.Dict.create())
        >> live.plane_to_plane_runs.init(nu.Dict.create())
        >> live.cell_to_cell_runs.init(nu.Dict.create())
        >> live.plane_run_to_cell_runs.init(nu.Dict.create())
        >> live.plane_run_to_failed_cells.init(nu.Dict.create())
        >> live.plane_run_to_workers.init(nu.Dict.create())
        >> live.workers.init(nu.Dict.create())
    )
