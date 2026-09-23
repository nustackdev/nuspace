"""Bootstrap: the service planes made real in a store, once.

Each service is a system plane with a fixed id and one cell ``main`` whose
prog is the service's shim (D20, D31). init's boot list is seeded with the
others the first time, and left alone after: it is data somebody may have
edited since.
"""

from __future__ import annotations

import nu
from nuspace.ops import add_cell, add_plane
from nuspace.ops.utils import atomic
from nuspace.shapes import Space

from ..utils import snap
from . import init, nav, reload, supervisor


__all__ = ["BOOTED", "SERVICES", "ensure_system"]


#: Every service, as ``(plane id, shim)``. init first: the kernel starts it.
SERVICES = (
    (init.PLANE, init.SHIM),
    (nav.PLANE, nav.SHIM),
    (supervisor.PLANE, supervisor.SHIM),
    (reload.PLANE, reload.SHIM),
)

#: What init's boot list starts as: every service but init itself.
BOOTED = init.BOOTED

#: Structural extras on a service plane: kept out of the shell.
META = {"ui": False}


def _service(plane_id: str, shim: str) -> nu.Nu:
    """A service plane and its cell, each made only when missing.

    Only when missing, because ``add_plane`` on an existing id rewrites its
    name and flags, and ``add_cell`` its prog. Missing means never made by
    those ops, not an absent row: :func:`~.init.boot` before the first open
    writes init's cell state, which leaves a row with no name and no prog.
    """
    row = Space.planes[plane_id]
    return nu.IfDo(
        snap(nu.Not(row.contains("name"))),
        add_plane(plane_id, name=plane_id, system=True, meta=META),
    ) >> nu.IfDo(
        snap(nu.Not(row.cells[init.CELL].contains("prog"))),
        add_cell(plane_id, shim, cell_id=init.CELL, name=init.CELL),
    )


def ensure_system() -> nu.Nu:
    """The service planes, and init's boot list, where missing. Idempotent.

    A store that has them is left exactly as it is. Run before the kernel
    starts init (``open_kernel(init="init")``).
    """
    term = _service(*SERVICES[0])
    for plane_id, shim in SERVICES[1:]:
        term = term >> _service(plane_id, shim)
    return term >> atomic(init.seed(list(BOOTED)))
