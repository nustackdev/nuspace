"""Bootstrap: the service planes made real in a store, once.

Each service is a system plane with a fixed id and one cell ``main`` whose
prog is the service's shim (D20, D31). init's boot list is seeded with the
others the first time, and left alone after: it is data somebody may have
edited since.
"""

from __future__ import annotations

import nu
from nuspace.ops.cell import HasUi, cell_writes
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import atomic, atomic_state
from nuspace.shapes import Space

from ..utils import snap
from . import init, nav, reactions, reload, supervisor


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


def _service(plane_id: str, shim: str) -> nu.Nu:
    """A service plane and its cell, each made only when missing, in one commit. On ``mp``.

    Only when missing, because ``add_plane`` on an existing id rewrites its
    name and props, and ``add_cell`` its prog. Missing means never made by
    those ops, not an absent row: a row can be there with no name and no
    prog (eg written by hand). The cell's ``has_ui`` is worked out first,
    outside the bracket, and only when the cell is missing.
    """
    row = Space.planes[plane_id]
    no_plane = nu.Not(row.contains("name"))
    no_cell = nu.Not(row.cells[init.CELL].contains("prog"))
    made = nu.IfDo(no_plane, plane_writes(plane_id, backend="mp", name=plane_id, system=True))

    def both(ui: nu.ObjectRef) -> nu.Nu:
        cell = cell_writes(plane_id, init.CELL, shim, nu.Bool(ui), name=init.CELL)
        return atomic(made >> nu.IfDo(no_cell, cell))

    return nu.IfDo(snap(nu.Or(no_plane, no_cell)), nu.let(HasUi(shim, plane_id, init.CELL), both))


def ensure_system() -> nu.Nu:
    """The service planes, the reactions plane, and init's boot list, where missing. Idempotent.

    A store that has them is left exactly as it is. Run before the kernel
    starts init (``open_kernel(init="init")``).
    """
    term = _service(*SERVICES[0])
    for plane_id, shim in SERVICES[1:]:
        term = term >> _service(plane_id, shim)
    return term >> reactions.ensure_reactions() >> atomic_state(init.seed(list(BOOTED)))
