"""out: a run's stdout and stderr, captured in the worker, flushed to its record.

Many runs share one worker process and one ``sys.stdout``, so lines are
attributed by a contextvar: :class:`Captured` sets it to the run's own
:class:`RunOut` around the body, every task the body starts inherits it,
and a tee on ``sys.stdout`` and ``sys.stderr`` appends what is written while
it is set. ``nu.Print`` falls back to ``sys.stdout``, so it lands too.

What it misses: writes from threads that did not copy the context (a
library's own thread pool), and output of C extensions writing to fd 1
directly. Those still reach the worker's real stdout, just not ``out``.

The buffer is a ring of the last :data:`OUT_CAP` lines. ``Run.out`` is a
value list with one writer, the run's own body (D24), so the body writes the
ring whole (:class:`TakeOut`) and never reads the record back.
"""

from __future__ import annotations

import contextlib
import contextvars
import sys
import threading
import time
import traceback
from collections import deque
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING

from nu.context import FabricRef
from nu.core.spans.bracket import _LifecycleBracket
from nu.engine.structure import Declared
from nu.lang import ScalarAction, ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from nu.lang.runtime import Context, Runtime


__all__ = [
    "OUT_CAP",
    "STDERR",
    "STDOUT",
    "Captured",
    "ErrorText",
    "HasOut",
    "RunOut",
    "RunOutRef",
    "TakeOut",
]


#: How many entries ``Run.out`` keeps, newest last.
OUT_CAP = 200

#: The stream names an entry carries.
STDOUT = "stdout"
STDERR = "stderr"

_CURRENT: contextvars.ContextVar[RunOut | None] = contextvars.ContextVar(
    "nuspace_run_out", default=None
)
_INSTALL = threading.Lock()


class RunOut:
    """One run's output: a ring of its last :data:`OUT_CAP` lines. Thread safe.

    Entries are ``(ts, stream, text)``, one per line. Tuples, because they
    cross to the host by value where a list would cross as a reference. A
    write without a newline waits for the rest of its line, or for the final
    take. The run's body is the record's only writer, so the ring is the
    whole truth and a flush writes it whole, reading nothing back.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ring: deque[tuple] = deque(maxlen=OUT_CAP)
        self._partial: dict[str, str] = {}
        self._dirty = False

    def write(self, stream: str, text: str) -> None:
        """Append ``text`` written to ``stream``, split into lines."""
        with self._lock:
            pending = self._partial.pop(stream, "") + text
            *lines, rest = pending.split("\n")
            now = time.time()
            self._ring.extend((now, stream, line) for line in lines)
            self._dirty = self._dirty or bool(lines)
            if rest:
                self._partial[stream] = rest

    def note(self, stream: str, text: str) -> None:
        """Append ``text`` as one entry, whatever it holds."""
        with self._lock:
            self._ring.append((time.time(), stream, text))
            self._dirty = True

    @property
    def pending(self) -> bool:
        """Whether a line came in since the last take."""
        with self._lock:
            return self._dirty

    def take(self, *, final: bool = False) -> tuple:
        """The whole ring, marked flushed. With ``final``, unfinished lines too."""
        with self._lock:
            if final:
                now = time.time()
                self._ring.extend((now, s, t) for s, t in self._partial.items())
                self._partial.clear()
            self._dirty = False
            return tuple(self._ring)


class RunOutRef(FabricRef):
    """The :class:`RunOut` bound on the context. EMPTY outside a run."""

    fabric = RunOut


class _Tee:
    """Stands in for ``sys.stdout`` or ``sys.stderr``: writes through, and to the current run."""

    def __init__(self, stream: str, real: object) -> None:
        self._stream = stream
        self._real = real

    def write(self, text: str) -> int:
        out = _CURRENT.get()
        if out is not None:
            out.write(self._stream, text)
        return self._real.write(text)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


def install() -> None:
    """Put the tee on this process's ``sys.stdout`` and ``sys.stderr``. Idempotent."""
    with _INSTALL:
        if not isinstance(sys.stdout, _Tee):
            sys.stdout = _Tee(STDOUT, sys.stdout)  # type: ignore[assignment]
        if not isinstance(sys.stderr, _Tee):
            sys.stderr = _Tee(STDERR, sys.stderr)  # type: ignore[assignment]


class Captured(_LifecycleBracket):
    """Capture the body's output into a fresh :class:`RunOut`, bound on the context.

    A bracket for ``nu.With``. Only meaningful on a loop: the contextvar
    follows tasks, and a sync body offloaded to a thread follows only if the
    thread copied the context (nu's own pool does).
    """

    @contextmanager
    def _open(self, ctx: Context) -> Iterator[Context]:
        """Sync form: bind the buffer, attribute nothing."""
        yield ctx.bind(RunOut, RunOut())

    @asynccontextmanager
    async def _aopen(self, ctx: Context) -> AsyncIterator[Context]:
        """Tee the process, point the contextvar at a fresh buffer, bind it."""
        install()
        out = RunOut()
        token = _CURRENT.set(out)
        try:
            yield ctx.bind(RunOut, out)
        finally:
            with contextlib.suppress(ValueError):
                _CURRENT.reset(token)


def _value(v: object, default: object) -> object:
    return default if v is EMPTY or v is INVALID or v is None else v


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


class HasOut(_Pure):
    """Whether the run has lines not yet flushed. False outside a run."""

    def __init__(self) -> None:
        super().__init__(RunOutRef())

    def _apply(self, out: object) -> object:
        return isinstance(out, RunOut) and out.pending


class TakeOut(ScalarAction):
    """The run's output so far, what ``Run.out`` is set to. Marks it flushed.

    Args:
        extra: Text appended first as one stderr entry, eg a traceback.
            EMPTY or "" appends nothing.
        final: Take unfinished lines too.

    Yields:
        A tuple of ``(ts, stream, text)``, ``()`` outside a run.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, extra: object = "", *, final: bool = False) -> None:
        super().__init__(RunOutRef(), extra)
        self._payload["final"] = final

    def _take(self, out: object, extra: object) -> tuple:
        if not isinstance(out, RunOut):
            return ()
        extra = _value(extra, "")
        if extra:
            out.note(STDERR, str(extra))
        return out.take(final=self._payload["final"])

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
