"""The backend fabric: what every backend is, how the kernel reaches one, what it records.

A backend executes plane runs. Each is a fabric, one instance per name,
bound on the host's context at open under :class:`Backend` tagged with its
name. The kernel reads one with ``BackendRef(name)``, the name off the plane
run's record, and speaks to it only through the interactions here, so it
never asks what kind it holds::

    StartRun(ref, run)             a plane run begins            -> made
    PlaceCell(ref, run, cr)        where a cell run goes          -> [worker, made]
    RunCell (kernel)               its body run there, to its end -> "" or why it was lost
    EndCell(ref, run, cr)          a cell run is over             -> [worker let go]
    KillRun(ref, run)              the plane run is over          -> [worker let go]

``made`` is ``[[worker, handle], ...]``, the workers a call brought up. A
worker is whatever unit the backend runs cells on (a process here, anything
later), its ``handle`` a str only the backend reads.

Workers are records the backends write and everybody reads (:func:`start`,
:func:`placed`, :func:`lost`, :func:`end_cell`, :func:`kill`): the terms here
pair each interaction with its record writes, so no backend is ever half
recorded. The kernel only composes :func:`released` into the commit that
ends a plane run, so its workers end with it.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import nu
from nu.context import FabricRef
from nu.engine.structure import Declared
from nu.lang import ScalarAction
from nu.lang.sentinels import EMPTY
from nuspace.ops.utils import atomic, fresh
from nuspace.shapes import EXIT_FAILED, Space
from nuspace.system.kernel.utils import Now


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = [
    "Backend",
    "BackendRef",
    "EndCell",
    "KillRun",
    "PlaceCell",
    "StartRun",
    "UnknownBackendError",
    "end_cell",
    "kill",
    "lost",
    "placed",
    "released",
    "require_backend",
    "start",
]


_kernel = Space.kernel


class UnknownBackendError(LookupError):
    """A plane run names a backend nobody registered."""


class Backend:
    """What executes plane runs. Subclass it, register the subclass by name at open.

    Every method is async and runs in the host. Worker ids are minted by the
    backend (``mint_ordered_id("w")``), and each method says which workers
    it brought up or let go, so the record writes around it stay generic.

    A backend's bookkeeping (its handles, which cell run is where) is its
    own. The kernel keeps none of it.
    """

    async def astart(self, run_id: str) -> list[list[str]]:
        """Get ready to run cells for a new plane run. The workers brought up."""
        raise NotImplementedError

    async def aplace(self, run_id: str, cell_run_id: str) -> list:
        """Pick where a cell run goes, before its body exists. ``[worker, made]``."""
        raise NotImplementedError

    async def arun(self, run_id: str, cell_run_id: str, body: nu.Nu) -> str:
        """Run a placed cell run's body on its worker, and return once it has ended.

        ``""`` when the body ran to its end, which it writes itself. Why,
        when the worker died under it by itself: the kernel ends the cell run
        and the worker ``failed`` with that. A worker the backend let go on
        purpose is not a loss: whoever let it go ends what ran there.

        Cancelled, the body is cancelled where it runs.
        """
        raise NotImplementedError

    async def aend_cell(self, run_id: str, cell_run_id: str) -> list[str]:
        """A cell run is over. The workers let go because of it."""
        raise NotImplementedError

    async def akill(self, run_id: str) -> list[str]:
        """Tear the plane run down. The workers let go. Idempotent."""
        raise NotImplementedError


class BackendRef(FabricRef):
    """The :class:`Backend` bound under ``name`` on the context.

    Where none is, it yields a stand-in carrying the name, which every
    interaction refuses with :class:`UnknownBackendError` naming it.

    Args:
        name: The registered name, any ``StrArg``: the kernel passes the one
            on the plane run's record.
    """

    fabric = Backend

    def __init__(self, name: nu.StrArg) -> None:
        # Two children, the fabric type and the name, where FabricRef has one.
        super(FabricRef, self).__init__(Backend, name)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        fabric, name = children

        def thunk(rt: Runtime) -> object:
            f, n = fabric(rt), name(rt)
            return rt.ctx.fabrics.get(f, n) if rt.ctx.fabrics.has(f, n) else _Named(n)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        fabric, name = children

        async def athunk(rt: Runtime) -> object:
            f, n = await fabric(rt), await name(rt)
            return rt.ctx.fabrics.get(f, n) if rt.ctx.fabrics.has(f, n) else _Named(n)

        return athunk


class _Named:
    """What :class:`BackendRef` yields for a name nothing is bound under, so the refusal names it."""

    __slots__ = ("name",)

    def __init__(self, name: object) -> None:
        self.name = name


def require_backend(value: object) -> Backend:
    """Unwrap a :class:`BackendRef`'s value.

    Raises:
        UnknownBackendError: No backend is bound under the name, or none is named.
    """
    if isinstance(value, Backend):
        return value
    name = value.name if isinstance(value, _Named) else value
    if name is EMPTY or name == "":
        msg = "The plane names no backend: every plane must name one, eg mp or async"
        raise UnknownBackendError(msg)
    msg = f"No backend registered as {name!r}"
    raise UnknownBackendError(msg)


# --- Interactions ------------------------------------------------------------------


class _Call(ScalarAction):
    """A backend method, awaited with the children after the ref. Async only.

    ``_shielded`` calls run to the end even when the caller is cancelled
    halfway: letting workers go must not stop at half, or a process outlives
    the run it served.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _method = ""
    _shielded = False

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        name = type(self).__name__

        def thunk(rt: Runtime) -> object:
            msg = f"{name} runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method, shielded = self._method, self._shielded

        async def athunk(rt: Runtime) -> object:
            backend = require_backend(await children[0](rt))
            args = [await child(rt) for child in children[1:]]
            call = getattr(backend, method)(*args)
            return await (asyncio.shield(call) if shielded else call)

        return athunk


class StartRun(_Call):
    """:meth:`Backend.astart`. Yields the workers brought up."""

    _method = "astart"

    def __init__(self, backend: nu.Nu, run_id: nu.StrArg) -> None:
        super().__init__(backend, run_id)


class PlaceCell(_Call):
    """:meth:`Backend.aplace`. Yields ``[worker, made]``."""

    _method = "aplace"

    def __init__(self, backend: nu.Nu, run_id: nu.StrArg, cell_run_id: nu.StrArg) -> None:
        super().__init__(backend, run_id, cell_run_id)


class EndCell(_Call):
    """:meth:`Backend.aend_cell`. Yields the workers let go. Shielded."""

    _method = "aend_cell"
    _shielded = True

    def __init__(self, backend: nu.Nu, run_id: nu.StrArg, cell_run_id: nu.StrArg) -> None:
        super().__init__(backend, run_id, cell_run_id)


class KillRun(_Call):
    """:meth:`Backend.akill`. Yields the workers let go. Shielded."""

    _method = "akill"
    _shielded = True

    def __init__(self, backend: nu.Nu, run_id: nu.StrArg) -> None:
        super().__init__(backend, run_id)


# --- Records -------------------------------------------------------------------


def _made(backend: nu.StrArg, run_id: nu.StrArg, made: nu.Nu) -> nu.Nu:
    """Worker records for ``[[worker, handle], ...]``, live. No bracket.

    A worker whose end landed first (it died before this commit) keeps its
    end and stays out of ``workers_running``.
    """
    item = fresh("made")
    pair = nu.List(nu.Attr(item))
    wid = nu.ToStr(pair[0])
    row = _kernel.workers[wid]
    write = (
        row.backend.set(backend)
        >> row.run.set(run_id)
        >> row.handle.set(nu.ToStr(pair[1]))
        >> row.started_at.set(Now())
        >> _kernel.runs[run_id].workers.add(wid)
        >> nu.IfDo(nu.Not(row.terminated_at.exists()), _kernel.workers_running.add(wid))
    )
    return nu.ForEachDo(nu.List(made), write, item=item)


def _ended(worker_id: nu.StrArg, exit_: nu.StrArg, error: nu.StrArg = "") -> nu.Nu:
    """A worker's end, written once, and out of ``workers_running``. No bracket."""
    row = _kernel.workers[worker_id]
    return nu.IfDo(
        nu.Not(row.terminated_at.exists()),
        row.terminated_at.set(Now()) >> row.exit.set(exit_) >> row.error.set(error),
    ) >> nu.IfDo(
        _kernel.workers_running.contains(worker_id), _kernel.workers_running.discard(worker_id)
    )


def released(run_id: nu.StrArg, exit_: nu.StrArg) -> nu.Nu:
    """Every live worker of a plane run ended ``exit_``. No bracket.

    For the commit that ends the run: its workers' records end with it, so
    nothing is left to write once the kernel lets go of the run, however it
    is cancelled. The backend's own kill follows, and finds them ended.

    Walks ``workers_running``, the live workers, never the run's own
    ``workers``: with ``mp`` that is a worker per cell run ever.
    """
    item = fresh("released")
    wid = nu.Str(nu.Attr(item))
    mine = nu.Eq(nu.ToStr(_kernel.workers[wid].run), run_id)
    return nu.ForEachDo(
        nu.list(_kernel.workers_running), nu.IfDo(mine, _ended(wid, exit_)), item=item
    )


def _let_go(ids: nu.Nu, exit_: nu.StrArg) -> nu.Nu:
    """Every worker id in ``ids`` ended ``exit_``. One commit."""
    item = fresh("let_go")
    return atomic(nu.ForEachDo(nu.List(ids), _ended(nu.Str(nu.Attr(item)), exit_), item=item))


def start(backend: nu.StrArg, run_id: nu.StrArg) -> nu.Nu:
    """:class:`StartRun`, and the workers it brought up recorded. One commit for the records."""
    return nu.let(
        StartRun(BackendRef(backend), run_id), lambda made: atomic(_made(backend, run_id, made))
    )


def placed(backend: nu.StrArg, run_id: nu.StrArg, cell_run_id: nu.StrArg, place: nu.Nu) -> nu.Nu:
    """The cell run's ``worker`` and the workers ``place`` brought up, recorded. One commit.

    Args:
        backend: The backend's registered name.
        run_id: The plane run.
        cell_run_id: The cell run placed.
        place: ``[worker, made]``, what :class:`PlaceCell` yielded.
    """
    got = nu.List(place)
    cr = _kernel.runs[run_id].cells[cell_run_id]
    return atomic(cr.worker.set(nu.ToStr(got[0])) >> _made(backend, run_id, got[1]))


def lost(worker_id: nu.StrArg, why: nu.StrArg) -> nu.Nu:
    """A worker that died by itself, recorded ended ``failed`` with why. No bracket.

    For the commit that ends the cell run it took with it (``RunCell``
    yielded ``why``). Written once: with ``async``, every cell run on the
    worker reports the same death, and the first one writes it.
    """
    return _ended(worker_id, EXIT_FAILED, why)


def end_cell(
    backend: nu.StrArg, run_id: nu.StrArg, cell_run_id: nu.StrArg, exit_: nu.StrArg
) -> nu.Nu:
    """:class:`EndCell`, and the workers it let go recorded ended ``exit_``."""
    return nu.let(
        EndCell(BackendRef(backend), run_id, cell_run_id), lambda gone: _let_go(gone, exit_)
    )


def kill(backend: nu.StrArg, run_id: nu.StrArg, exit_: nu.StrArg) -> nu.Nu:
    """:class:`KillRun`, and the workers it let go recorded ended ``exit_``."""
    return nu.let(KillRun(BackendRef(backend), run_id), lambda gone: _let_go(gone, exit_))
