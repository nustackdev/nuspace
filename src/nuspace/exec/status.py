"""The section contract: what you ask to run, and what comes back.

**This module is the one home for both.** Every supervisor in nuspace
speaks these two types -- the out-of-process :class:`Supervisor`, the
in-process ``LocalSupervisor`` behind the pages surface, and the
``AppsSupervisor`` behind the apps surface. They have different
lifetimes on purpose (a page runs per viewer, an app runs once for the
space), but only one spelling of what a section is and how it reports.

## What you ask for

:class:`SectionSpec` -- an id and the source that evaluates to a tree.
``prefix`` is the path the unit owns. For a section that is a ui mount
prefix (``sections.<id>``); an app overrides it with a kv namespace,
because apps are headless.

## What comes back

The dict shape is fixed and shared with the browser driver::

    {"section_id": str,
     "state": "invalid"|"idle"|"starting"|"running"|"stopped"|"failed",
     "error": str | None,
     "started_at": float | None}

``invalid`` means the source never compiled and ``error`` carries the
``nu.prog`` ``Diagnostic``, message plus the line in the unit's own
source. ``failed`` means it constructed, ran and died, and ``error``
carries the runtime error. They are different things to a person, so
they are different states.

``section_id`` is the unit id whatever the unit is. The apps surface
puts an app id in it rather than inventing ``app_id``: apps and sections
are the same substance, and a second spelling is how the two drift
apart.

``started_at`` is when the **current** run reached ``running``:

- cleared on ``idle``, ``starting`` and ``invalid``. Nothing has started
  yet, so a leftover timestamp from the last run would be a lie.
- stamped on ``running``.
- kept through ``stopped`` and ``failed``. The block chrome wants to say
  how long it ran before it died, and a terminal state has no next run
  to confuse it with.

The two supervisors used to disagree here: the local one stamped at
``starting`` and kept it forever, the out-of-process one stamped at
``running`` and cleared it again on teardown. Stamp late, keep through
terminal states -- that is the only rule where every state's value
answers "when did the run you are looking at begin".

Mount fields hang off :class:`SectionStatus` but stay out of
``to_wire()`` -- the wire contract is exactly those four keys.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal


if TYPE_CHECKING:
    from collections.abc import AsyncIterator


__all__ = [
    "STATES",
    "SectionSpec",
    "SectionState",
    "SectionStatus",
    "StatusEvent",
    "StatusStream",
]


SectionState = Literal["invalid", "idle", "starting", "running", "stopped", "failed"]

STATES: tuple[str, ...] = ("invalid", "idle", "starting", "running", "stopped", "failed")

# States with no run behind them yet. Entering one clears `started_at`.
UNSTARTED: tuple[str, ...] = ("idle", "starting", "invalid")


@dataclass(frozen=True)
class SectionSpec:
    """What a supervisor is asked to run: an id and a source, nothing else."""

    section_id: str
    source: str
    prefix_override: str | None = None

    @property
    def prefix(self) -> str:
        """The path this unit owns. Path is the mounting mechanism."""
        return self.prefix_override or f"sections.{self.section_id}"


@dataclass
class SectionStatus:
    """Live status of one section."""

    section_id: str
    state: SectionState = "idle"
    error: str | None = None
    started_at: float | None = None
    fields: list[dict[str, Any]] = field(default_factory=list)
    compiled: bool = False

    def to_wire(self) -> dict[str, Any]:
        """The wire contract. Four keys, no more."""
        return {
            "section_id": self.section_id,
            "state": self.state,
            "error": self.error,
            "started_at": self.started_at,
        }


@dataclass(frozen=True)
class StatusEvent:
    """One status transition, stamped with its page and generation."""

    page_id: str
    generation: int
    status: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Flat payload for a ui driver."""
        return {"page_id": self.page_id, "generation": self.generation, **self.status}


class _Subscriber:
    """One reader of the status stream."""

    def __init__(self, stream: StatusStream) -> None:
        self._stream = stream
        self._queue: asyncio.Queue[StatusEvent | None] = asyncio.Queue()
        self._closed = False

    def __aiter__(self) -> AsyncIterator[StatusEvent]:
        return self._iter()

    async def _iter(self) -> AsyncIterator[StatusEvent]:
        while True:
            event = await self._queue.get()
            if event is None:
                return
            yield event

    async def get(self, timeout: float | None = None) -> StatusEvent | None:
        """Await the next event (``None`` once the stream closes)."""
        if timeout is None:
            return await self._queue.get()
        return await asyncio.wait_for(self._queue.get(), timeout)

    def close(self) -> None:
        """Detach from the stream; the iterator finishes."""
        if self._closed:
            return
        self._closed = True
        self._stream._drop(self)
        self._queue.put_nowait(None)

    def _push(self, event: StatusEvent) -> None:
        if not self._closed:
            self._queue.put_nowait(event)


class StatusStream:
    """Fan-out of status transitions to any number of subscribers.

    Unbounded queues on purpose: a slow ui driver must never wedge the
    supervisor, and status volume is bounded by section count times
    transitions, not by anything user code controls.
    """

    def __init__(self) -> None:
        self._subscribers: set[_Subscriber] = set()

    def subscribe(self) -> _Subscriber:
        """Return a fresh subscriber. Call ``close()`` when done."""
        sub = _Subscriber(self)
        self._subscribers.add(sub)
        return sub

    def publish(self, event: StatusEvent) -> None:
        """Fan one event out. Never blocks, never raises."""
        for sub in tuple(self._subscribers):
            sub._push(event)

    def close(self) -> None:
        """Finish every subscriber's iterator."""
        for sub in tuple(self._subscribers):
            sub.close()

    def _drop(self, sub: _Subscriber) -> None:
        self._subscribers.discard(sub)
