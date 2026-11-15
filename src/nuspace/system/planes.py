"""The system planes as a set: made where missing, and init started. What the host runs at open.

Each system plane has a minted id like any plane, a key code finds it by
(``nuspace.at.plane(KEY)``, ``ops.plane.keyed(KEY)``), a title, is
``system`` (remove refuses it, only it holds a reserved key) and holds
cells whose progs are short shims: the code lives in
``nuspace.system.<plane>``, the store holds the shim. init's boot list
starts as the other three, so init brings them up:

    host        ensure() >> start()
    init        boots supervisor, reload, reactions
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.ops.brackets import atomic
from nuspace.utils import MintId

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


#: Every system plane: ``(key, title, backend, ((cell name, prog), ...))``. init first.
PLANES = (
    (init.KEY, "Init", INIT_BACKEND, (("main", INIT_PROG),)),
    (supervisor.KEY, "Supervisor", SUPERVISOR_BACKEND, (("main", SUPERVISOR_PROG),)),
    (reload.KEY, "Reload", RELOAD_BACKEND, (("main", RELOAD_PROG),)),
    (reactions.KEY, "Reactions", REACTIONS_BACKEND, (("park", PARK_PROG),)),
)

#: What init's own plane run is recorded as ``by`` when :func:`start` asks for it.
BY = "host"


def _made(key: str, title: str, backend: str, cells: tuple[tuple[str, str], ...]) -> nu.Nu:
    """One system plane and its cells, minted ids, when no plane holds its key. One commit."""

    def made(minted: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(minted)
        adds = ops.plane.add(plane, key=key, name=title, backend=backend, system=True)
        for name, prog in cells:
            adds = adds >> ops.cell.add(plane, prog, name=name, fabrics=[])
        return adds

    return atomic(nu.IfDo(ops.plane.keyed(key) == "", nu.let(MintId("p"), made)))


def ensure() -> nu.Nu:
    """Every system plane and its cells, then their state's containers, made where missing.

    Idempotent: a plane is made only when no plane holds its key, and what
    is there is left exactly as it is, init's boot list included (it is data
    somebody may have edited). The boot list starts as the ids of
    :data:`~nuspace.system.init.BOOTED`'s planes the first time. One commit
    per plane, then one State commit.
    """
    made = nu.Sequential(*(_made(*spec) for spec in PLANES))
    booted = init.boot_list()
    first = nu.Sequential(
        booted.init({}),
        *(booted.set_item(ops.plane.keyed(key), True) for key in init.BOOTED),
    )
    state = (
        nu.IfDo(booted.exists().not_(), first)
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
    plane = ops.plane.keyed(init.KEY)
    idle = ops.plane_run.any_live(plane).not_()
    return atomic(nu.IfDo(idle, ops.plane_run.add(plane, by=by)))
