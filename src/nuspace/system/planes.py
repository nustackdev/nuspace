"""The system planes as a set: made where missing, and init started. What the host runs at open.

Each system plane has a fixed id, is ``system`` (remove refuses it) and
holds fixed cells whose progs are short shims: the code lives in
``nuspace.system.<plane>``, the store holds the shim. init's boot list
starts as the other three, so init brings them up:

    host        ensure() >> start()
    init        boots supervisor, reload, reactions
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.errors import Refused
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space
from nuspace.utils.checks import refuse

from . import init, reactions, reload, supervisor
from .init.plane import BACKEND as INIT_BACKEND
from .init.plane import PROG as INIT_PROG
from .reactions.plane import BACKEND as REACTIONS_BACKEND
from .reactions.plane import PARK_PROG
from .reload.plane import BACKEND as RELOAD_BACKEND
from .reload.plane import PROG as RELOAD_PROG
from .supervisor.plane import BACKEND as SUPERVISOR_BACKEND
from .supervisor.plane import PROG as SUPERVISOR_PROG


__all__ = ["BY", "PLANES", "ensure", "start"]


#: Every system plane: ``(plane id, backend, ((cell id, cell name, prog), ...))``. init first.
PLANES = (
    (init.PLANE, INIT_BACKEND, ((init.CELL, "main", INIT_PROG),)),
    (supervisor.PLANE, SUPERVISOR_BACKEND, ((supervisor.CELL, "main", SUPERVISOR_PROG),)),
    (reload.PLANE, RELOAD_BACKEND, ((reload.CELL, "main", RELOAD_PROG),)),
    (reactions.PLANE, REACTIONS_BACKEND, ((reactions.PARK, "park", PARK_PROG),)),
)

#: What init's own plane run is recorded as ``by`` when :func:`start` asks for it.
BY = "host"


def _made(plane: str, backend: str, cells: tuple[tuple[str, str, str], ...]) -> nu.Nu:
    """One system plane and its cells, each made only where missing. One commit.

    Raises:
        Refused: The id is held by a plane that is not system, or a cell id
            by a cell on another plane (a store from before the ids were
            reserved).
    """
    rows = Space.planes
    there = ops.plane.exists(plane, removed=True)
    alien = there.and_(rows[plane].system.fallback(False).not_())
    term = refuse(alien, Refused, "plane ", plane, " is taken by a plane that is not system")
    term = term >> nu.IfDo(
        there.not_(), ops.plane.add(plane, name=plane, backend=backend, system=True)
    )
    for cell, name, prog in cells:
        held = Space.cells.contains(cell)
        elsewhere = held.and_(Space.cells[cell].plane.fallback("") != plane)
        term = (
            term
            >> refuse(elsewhere, Refused, "cell ", cell, " is taken by a cell of another plane")
            >> nu.IfDo(held.not_(), ops.cell.add(plane, prog, id=cell, name=name, fabrics=[]))
        )
    return atomic(term)


def ensure() -> nu.Nu:
    """Every system plane and its cells, then their state's containers, made where missing.

    Idempotent: what is there is left exactly as it is, init's boot list
    included (it is data somebody may have edited). The boot list starts as
    :data:`~nuspace.system.init.BOOTED` the first time. One commit per
    plane, then one State commit.

    Raises:
        Refused: A system plane's or cell's id held by something else.
    """
    made = nu.Sequential(*(_made(*spec) for spec in PLANES))
    state = (
        init.boot_list().init(dict.fromkeys(init.BOOTED, True))
        >> supervisor.supervised().init({})
        >> reactions.registry().by_plane.init({})
    )
    return made >> atomic(state)


def start(*, by: nu.StrArg = BY) -> nu.Nu:
    """A plane run of init asked for, unless it has a live one. One commit. The kernel runs it.

    Args:
        by: Who asks, what the run is recorded as.

    Raises:
        Missing: No init plane: :func:`ensure` first.
    """
    idle = ops.plane_run.any_live(init.PLANE).not_()
    return atomic(nu.IfDo(idle, ops.plane_run.add(init.PLANE, by=by)))
