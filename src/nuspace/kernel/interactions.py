"""The kernel's own nu interactions. The driver and the body are composed of these and the ops.

- :class:`KernelConfigRef`: the env registry bound at open.
- :class:`Body`: a cell run's body, built in the host from its record.
- :class:`Captured`: a bracket capturing a body's output, in the worker.
- :class:`HasOut`, :class:`TakeOut`: the output not written yet.
- :class:`ErrorText`: a caught error as text.

The backend calls are in :mod:`nuspace.kernel.backends.interactions`.
"""

from __future__ import annotations

import contextlib
import traceback
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING

from nu.context import FabricRef
from nu.core.spans.bracket import _LifecycleBracket
from nu.engine.structure import Declared
from nu.lang import ScalarAction, ScalarQuery, is_null

from . import out as _out
from .envs import KernelConfig


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    import nu
    from nu.lang.runtime import Context, Runtime


__all__ = [
    "Body",
    "Captured",
    "ErrorText",
    "HasOut",
    "KernelConfigRef",
    "RunOutRef",
    "TakeOut",
]


class KernelConfigRef(FabricRef):
    """The :class:`~.envs.KernelConfig` bound on the context. NULL when none is."""

    fabric = KernelConfig


class RunOutRef(FabricRef):
    """The :class:`~.out.RunOut` bound on the context. NULL outside a cell run."""

    fabric = _out.RunOut


def _value(v: object, default: object) -> object:
    return default if v is None or is_null(v) else v


class _Pure(ScalarQuery):
    """A query computed from its children's values by :meth:`_apply`."""

    def _apply(self, *values: object) -> object:
        raise NotImplementedError

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            return self._apply(*(c(rt) for c in children))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            return self._apply(*[await c(rt) for c in children])

        return athunk


class Body(_Pure):
    """A cell run's whole life on its worker, as a term: :func:`~.body.build_body`. Host only.

    Resolves the plane run's env specs through the
    :class:`~.envs.KernelConfig` on the context (none bound resolves no
    spec and refuses any), then builds the body. The wraps run here, so
    their lambdas never cross; the term built is what the backend runs.

    Args:
        plane_run: The plane run's id.
        cell_run: The cell run's id.
        plane: The plane id.
        cell: The cell id.
        envs: The plane run's env specs, ``[name, *args]`` each.

    Yields:
        The body, a picklable term.

    Raises:
        UnknownEnvError: A spec names no registered env.
    """

    def __init__(
        self,
        plane_run: nu.StrArg,
        cell_run: nu.StrArg,
        plane: nu.StrArg,
        cell: nu.StrArg,
        envs: object,
    ) -> None:
        super().__init__(KernelConfigRef(), plane_run, cell_run, plane, cell, envs)

    def _apply(self, *values: object) -> object:
        # The body imports these interactions, so it is reached at run time.
        from .body import build_body

        config, plane_run, cell_run, plane, cell, specs = values
        if not isinstance(config, KernelConfig):
            config = KernelConfig()
        envs = config.resolve(_value(specs, []))
        return build_body(str(plane_run), str(cell_run), str(plane), str(cell), envs)


class Captured(_LifecycleBracket):
    """Capture the body's output into a fresh :class:`~.out.RunOut`, bound on the context.

    A bracket for ``nu.With``. Only meaningful on a loop: the contextvar
    follows tasks, and a sync body offloaded to a thread follows only if the
    thread copied the context (nu's own pool does).
    """

    @contextmanager
    def _open(self, ctx: Context) -> Iterator[None]:
        """Sync form: bind the buffer, attribute nothing."""
        with ctx.fabrics.bind(_out.RunOut, _out.RunOut()):
            yield

    @asynccontextmanager
    async def _aopen(self, ctx: Context) -> AsyncIterator[None]:
        """Tee the process, point the contextvar at a fresh buffer, bind it."""
        _out.install()
        held = _out.RunOut()
        token = _out.current.set(held)
        try:
            with ctx.fabrics.bind(_out.RunOut, held):
                yield
        finally:
            with contextlib.suppress(ValueError):
                _out.current.reset(token)


class HasOut(_Pure):
    """Whether the cell run has whole lines not written yet. False outside a cell run."""

    def __init__(self) -> None:
        super().__init__(RunOutRef())

    def _apply(self, held: object) -> object:
        return isinstance(held, _out.RunOut) and held.pending


class TakeOut(ScalarAction):
    """The cell run's output not written yet, what ``CellRun.out`` is extended with.

    Marks it taken.

    Args:
        extra: Text appended first as one stderr entry, eg a traceback.
            NULL or "" appends nothing.
        final: Take unfinished lines too.

    Yields:
        A list of ``[ts, stream, text]``, ``[]`` outside a cell run.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, extra: object = "", *, final: bool = False) -> None:
        super().__init__(RunOutRef(), extra)
        self._payload["final"] = final

    def _take(self, held: object, extra: object) -> list:
        if not isinstance(held, _out.RunOut):
            return []
        extra = _value(extra, "")
        if extra:
            held.note(_out.STDERR, str(extra))
        return held.take(final=self._payload["final"])

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> object:
            return self._take(children[0](rt), children[1](rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> object:
            return self._take(await children[0](rt), await children[1](rt))

        return athunk


class ErrorText(_Pure):
    """A caught error as text: ``Type: message``, or its whole traceback.

    Args:
        error: What ``TryCatch`` bound, a ``CaughtError``.
        full: The traceback rather than the one line.
    """

    def __init__(self, error: object, *, full: bool = False) -> None:
        super().__init__(error)
        self._payload["full"] = full

    def _apply(self, error: object) -> object:
        exc = getattr(error, "exception", None)
        if exc is None:
            return str(_value(error, ""))
        if self._payload["full"]:
            return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        text = str(exc)
        return f"{type(exc).__name__}: {text}" if text else type(exc).__name__
