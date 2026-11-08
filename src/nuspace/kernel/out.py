"""out: a cell run's stdout and stderr, captured in the worker, line by line.

Many cell runs share one worker process and one ``sys.stdout``, so lines
are told apart by a contextvar: :class:`~.interactions.Captured` sets it to
the cell run's own :class:`RunOut` around the body, every task the body
starts inherits it, and a tee on ``sys.stdout`` and ``sys.stderr`` appends
what is written while it is set. ``nu.Print`` falls back to
``sys.stdout``, so it lands too.

What it misses: writes from threads that did not copy the context (a
library's own thread pool), and output of C extensions writing to fd 1
directly. Those still reach the worker's real stdout, but not ``out``.

``CellRun.out`` is a ring in the store that keeps the last
:data:`~nuspace.shapes.cell_run.OUT_CAP` entries, one writer: the cell
run's own body. So a :class:`RunOut` only holds the lines not written yet,
and each flush appends those to the ring.
"""

from __future__ import annotations

import contextvars
import sys
import threading
import time
from collections import deque

from nuspace.shapes.cell_run import OUT_CAP


__all__ = ["STDERR", "STDOUT", "RunOut", "current", "install"]


#: The stream names an entry carries.
STDOUT = "stdout"
STDERR = "stderr"

#: The cell run whose output this task writes, None outside one.
current: contextvars.ContextVar[RunOut | None] = contextvars.ContextVar(
    "nuspace_run_out", default=None
)
_INSTALL = threading.Lock()


class RunOut:
    """One cell run's output not yet in the store. Thread safe.

    Entries are ``[ts, stream, text]``, one per line, the shape of a
    ``CellRun.out`` entry. A write without a newline waits for the rest of
    its line, or for the final take. Holds at most
    :data:`~nuspace.shapes.cell_run.OUT_CAP` entries, as the ring does: past
    it the oldest drop before they are ever written.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pending: deque[list] = deque(maxlen=OUT_CAP)
        self._partial: dict[str, str] = {}

    def write(self, stream: str, text: str) -> None:
        """Append ``text`` written to ``stream``, split into lines."""
        with self._lock:
            pending = self._partial.pop(stream, "") + text
            *lines, rest = pending.split("\n")
            now = time.time()
            self._pending.extend([now, stream, line] for line in lines)
            if rest:
                self._partial[stream] = rest

    def note(self, stream: str, text: str) -> None:
        """Append ``text`` as one entry, whatever it holds."""
        with self._lock:
            self._pending.append([time.time(), stream, text])

    @property
    def pending(self) -> bool:
        """Whether a whole line came in since the last take."""
        with self._lock:
            return bool(self._pending)

    def take(self, *, final: bool = False) -> list[list]:
        """The entries not taken yet, oldest first. With ``final``, unfinished lines too."""
        with self._lock:
            if final:
                now = time.time()
                self._pending.extend([now, s, t] for s, t in self._partial.items())
                self._partial.clear()
            taken = list(self._pending)
            self._pending.clear()
            return taken


class _Tee:
    """Stands in for ``sys.stdout`` or ``sys.stderr``: writes through, and to the current cell run."""

    def __init__(self, stream: str, real: object) -> None:
        self._stream = stream
        self._real = real

    def write(self, text: str) -> int:
        out = current.get()
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
