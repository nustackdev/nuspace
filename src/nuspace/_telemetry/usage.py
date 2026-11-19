"""Usage: telemetry as nu terms, told once the term runs.

- :func:`track`: one event by name, eg ``track("plane_created")``, handed
  to :func:`nuspace._telemetry.track`. O(1): it queues and returns, never
  sends. Whether anything leaves the machine is the sender's call (opt out,
  dev install, CI), so it runs the same in the host, a worker or a
  script.
- :func:`opened`: a space opened, told once per open by the host.

The core ops tell what they make and remove themselves, as the last step
of their own term, reading no key for it (:func:`created`). A commit
retried on conflict is told again: telemetry is read as trends. An event is its name alone, never a name, an id,
a count or a source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.engine.structure import Declared
from nu.lang import Command, Ref


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["TELEMETRY", "TelemetryRef", "Track", "created", "opened", "track"]


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
    """Queue the event, through the :data:`TELEMETRY` Ref in slot 0. Never raises.

    ``""`` is the open: :func:`nuspace._telemetry.opened`. Anything else is
    one event, :func:`nuspace._telemetry.track`.

    Args:
        ref: :data:`TELEMETRY`.
        event: What happened: a str, or any Nu yielding one. A config child.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, ref: TelemetryRef, event: str) -> None:
        super().__init__(ref, event)

    @staticmethod
    def _tell(event: str) -> None:
        # Imported on first tell, never on import: importing nuspace reaches no telemetry.
        from nuspace import _telemetry

        if event:
            _telemetry.track(event)
        else:
            _telemetry.opened()

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        event = children[1]

        def thunk(rt: Runtime) -> None:
            self._tell(event(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        event = children[1]

        async def athunk(rt: Runtime) -> None:
            self._tell(await event(rt))

        return athunk


def track(event: str) -> Track:
    """Queue ``event`` as nuspace's own, eg ``plane_created``. Never raises, never waits.

    Args:
        event: What happened, a plain str.
    """
    return Track(TELEMETRY, event)


def opened() -> Track:
    """A space opened: the id made if missing, then ``first_run`` and ``space_opened``. Never raises.

    Run by the kernel before any cell runs, so the anonymous id is made here,
    once, and never by two workers racing to make their own.
    """
    return Track(TELEMETRY, "")


def created(what: str, *, system: nu.BoolArg = False, spec: nu.StrArg = "") -> nu.Nu:
    """``<what>_created_system``, ``<what>_created_spec`` or ``<what>_created``. Reads no key.

    Picked from the args at build when they are literals, else from their
    values when the term runs.

    Args:
        what: ``plane`` or ``cell``.
        system: Made by nuspace itself.
        spec: The spec it was made from, ``""`` for none.
    """
    plain = track(f"{what}_created")
    by_spec = track(f"{what}_created_spec")
    by_system = track(f"{what}_created_system")
    if isinstance(spec, str):
        not_system = by_spec if spec else plain
    else:
        not_system = nu.IfDo(nu.Str(spec) != "", by_spec, plain)
    if isinstance(system, bool):
        return by_system if system else not_system
    return nu.IfDo(nu.bool(system), by_system, not_system)
