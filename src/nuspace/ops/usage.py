"""Usage: the ops that make and remove planes and cells say so, once their commit lands.

- :func:`track`: one event by name, eg ``track("plane_created")``, handed
  to :func:`nuspace._telemetry.track`. O(1): it queues and returns, never
  sends. Whether anything leaves the machine is the sender's call (opt out,
  dev install, CI), so it runs the same in the host, a worker or a
  script.
- :func:`opened`: a space opened, told once per open by the host.

Each op tracks after its own commit, never inside it, so a retried commit
is told once, and only when it made or removed something. Only what is the
user's is told: a system plane and the cells on one never are. A write
that goes round the ops is not told at all: this is the trend, not a count.
An event is its name alone, never a name, an id, a count or a source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nu.engine.structure import Declared
from nu.lang import Command, Ref


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["TELEMETRY", "TelemetryRef", "Track", "opened", "track"]


class TelemetryRef(Ref):
    """The Ref naming telemetry's queue, the fabric :class:`Track` writes. One singleton.

    Like nu's stdio Refs: nothing is bound, the write goes straight to
    :mod:`nuspace._telemetry`. Declared so the engine keeps tracks ordered
    and never folds one away as a pure read.

    Yields:
        None.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        return lambda rt: None

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> None:
            return None

        return athunk


#: The one telemetry Ref.
TELEMETRY = TelemetryRef()


class Track(Command):
    """Queue the event in the payload, through the :data:`TELEMETRY` Ref in slot 0. Never raises.

    ``""`` is the open: :func:`nuspace._telemetry.opened`. Anything else is
    one event, :func:`nuspace._telemetry.track`.

    Args:
        ref: :data:`TELEMETRY`.
        event: What happened, a plain str.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, ref: TelemetryRef, event: str) -> None:
        super().__init__(ref)
        self._payload = dict(self._payload)
        self._payload["event"] = event

    def _tell(self) -> None:
        # Imported on first tell, never on import: importing nuspace reaches no telemetry.
        from nuspace import _telemetry

        event = self._payload["event"]
        if event:
            _telemetry.track(event)
        else:
            _telemetry.opened()

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            self._tell()

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> None:
            self._tell()

        return athunk


def track(event: str) -> Track:
    """Queue ``event`` as nuspace's own, eg ``plane_created``. Never raises, never waits.

    Args:
        event: What happened, a plain str.
    """
    return Track(TELEMETRY, event)


def opened() -> Track:
    """A space opened: the id made if missing, then ``first_run`` and ``space_opened``. Never raises.

    Run by the host before any cell runs, so the anonymous id is made here,
    once, and never by two workers racing to make their own.
    """
    return Track(TELEMETRY, "")
