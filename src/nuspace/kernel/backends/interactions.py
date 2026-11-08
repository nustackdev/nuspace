"""The nu interactions over a backend: how the kernel reaches one and calls it.

The kernel reads a backend with :class:`BackendRef`, by the name on the
plane run's record, and calls it only through these, so it never asks what
kind it holds::

    Placement(ref)                  when it wants a worker      -> "plane_run" | "cell_run"
    Launch(ref, worker)             bring a worker up           -> handle
    Run(ref, worker, cell_run, body) run a body there, to its end -> "" or why it was lost
    Stop(ref, workers)              let workers go              (shielded)
    Kill(ref, workers)              tear workers down now       (shielded)

All async only: backends run on the host's loop. :class:`Stop` and
:class:`Kill` take a list of worker ids and are shielded: letting go never
stops halfway when the caller is cancelled, or a process outlives the run
it served. An empty list does nothing, not even look the backend up, so a
run whose backend was never found lets go of nothing cleanly.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from nu.context import FabricRef
from nu.engine.structure import Declared
from nu.lang import Command, ScalarAction, ScalarQuery, is_null

from .base import Backend, require_backend


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu
    from nu.lang.runtime import Runtime


__all__ = ["BackendRef", "Kill", "Launch", "Placement", "Run", "Stop"]


class _Named:
    """What :class:`BackendRef` yields for a name nothing is bound under, so the refusal names it."""

    __slots__ = ("name",)

    def __init__(self, name: object) -> None:
        self.name = name


class BackendRef(FabricRef):
    """The :class:`~.base.Backend` bound under ``name`` on the context.

    Where none is, it yields a stand-in carrying the name, which every
    interaction refuses with :class:`~.base.UnknownBackendError` naming it.

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


def _sync(name: str) -> Callable:
    def thunk(rt: Runtime) -> object:
        msg = f"{name} runs on a loop; use arun"
        raise RuntimeError(msg)

    return thunk


class Placement(ScalarQuery):
    """The backend's placement: when the kernel wants a worker. A read of a class attribute.

    Raises:
        UnknownBackendError: No backend is registered under the name.
    """

    def __init__(self, backend: nu.Nu) -> None:
        super().__init__(backend)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            return require_backend(children[0](rt)).placement

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            return require_backend(await children[0](rt)).placement

        return athunk


class _Call(ScalarAction):
    """A backend method, awaited with the children after the ref. Async only."""

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _method = ""

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        return _sync(type(self).__name__)

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self._method

        async def athunk(rt: Runtime) -> object:
            backend = require_backend(await children[0](rt))
            args = [await child(rt) for child in children[1:]]
            return await getattr(backend, method)(*args)

        return athunk


class Launch(_Call):
    """:meth:`~.base.Backend.alaunch`: a worker up under the minted id. Yields its handle."""

    _method = "alaunch"

    def __init__(self, backend: nu.Nu, worker: nu.StrArg) -> None:
        super().__init__(backend, worker)


class Run(_Call):
    """:meth:`~.base.Backend.arun`: a cell run's body run on a worker, to its end.

    Yields ``""`` when the body ran to its end, or why its worker was lost.
    Cancelled, the backend cancels the body where it runs.
    """

    _method = "arun"

    def __init__(self, backend: nu.Nu, worker: nu.StrArg, cell_run: nu.StrArg, body: nu.Nu) -> None:
        super().__init__(backend, worker, cell_run, body)


async def _all(backend: Backend, method: str, workers: list[str]) -> None:
    """``method`` for every worker at once. Every call runs to its end; the first raise is raised."""
    calls = (getattr(backend, method)(w) for w in workers)
    results = await asyncio.gather(*calls, return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    if errors:
        raise errors[0]


def _late(workers: list[str]) -> Callable[[asyncio.Task], None]:
    """Report a let go that raised after its caller was cancelled: nobody else will see it."""

    def report(task: asyncio.Task) -> None:
        if task.cancelled() or task.exception() is None:
            return
        exc = task.exception()
        text = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        print(f"nuspace kernel let go of {', '.join(workers)}: {text}", file=sys.stdout)  # noqa: T201

    return report


class _LetGo(Command):
    """A backend method called for every worker in a list, all at once, shielded. Async only.

    Cancelled halfway, every call still runs to its end; a raise the
    cancelled caller can no longer see is reported on stdout.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _method = ""

    def __init__(self, backend: nu.Nu, workers: object) -> None:
        super().__init__(backend, workers)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        return _sync(type(self).__name__)

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self._method

        async def athunk(rt: Runtime) -> None:
            workers = await children[1](rt)
            ids = [] if workers is None or is_null(workers) else [str(w) for w in workers]
            if not ids:
                return
            backend = require_backend(await children[0](rt))
            task = asyncio.ensure_future(_all(backend, method, ids))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                task.add_done_callback(_late(ids))
                raise

        return athunk


class Stop(_LetGo):
    """:meth:`~.base.Backend.astop` for every worker in ``workers``. Shielded."""

    _method = "astop"


class Kill(_LetGo):
    """:meth:`~.base.Backend.akill` for every worker in ``workers``. Shielded."""

    _method = "akill"
