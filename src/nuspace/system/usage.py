"""Usage: what the host says about how the space is used, to whoever binds a :class:`Usage`.

A fabric, bound on the host's context by whoever wants to hear, eg the
command line's telemetry (:mod:`nuspace._telemetry`). Nothing binds one by
default, so a space opened from code, a test or a worker tells nobody, and
nuspace never reaches telemetry on its own.

- :class:`Track`: one event by name, eg ``Track("plane_created")``. Does
  nothing with no :class:`Usage` bound.
- :func:`watch`: planes and cells made and removed, by anyone, heard per
  id off the store's change feed. Runs beside the kernel.

Only what is the user's is told: a system plane (a service, home, settings)
and its cells never are, so the space setting itself up is not mistaken for
use. An event is its name alone, never a name, an id, a count or a source.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.context import FabricRef
from nu.engine.structure import Declared
from nu.lang import Command
from nuspace.ops.read import cell_exists, plane_exists
from nuspace.shapes import Space
from nuspace.system.kernel.utils import snap


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Track", "Usage", "UsageRef", "is_system", "watch"]


class Usage:
    """Hears what the host tracks and hands it to ``sink``. Never raises.

    Bound with ``nu.Provide(Usage, {"sink": fn})``. ``sink(event)`` runs on
    the space's loop, so it must return at once: queue, never send.

    Args:
        sink: What each event goes to. None hears nothing.
    """

    def __init__(self, sink: Callable[[str], None] | None = None) -> None:
        self._sink = sink

    def track(self, event: str) -> None:
        """Hand ``event`` to the sink."""
        if self._sink is None:
            return
        try:
            self._sink(event)
        except Exception:  # noqa: S110 -- usage never breaks the space
            pass


class UsageRef(FabricRef):
    """The :class:`Usage` bound on the context. EMPTY when none is."""

    fabric = Usage


class Track(Command):
    """Tell the bound :class:`Usage` that ``event`` happened. No-op with none bound.

    Args:
        event: What happened, eg ``"plane_created"``. A plain str.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, event: str) -> None:
        super().__init__(UsageRef())
        self._payload = dict(self._payload)
        self._payload["event"] = event

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        event = self._payload["event"]

        def thunk(rt: Runtime) -> None:
            usage = children[0](rt)
            if isinstance(usage, Usage):
                usage.track(event)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        event = self._payload["event"]

        async def athunk(rt: Runtime) -> None:
            usage = await children[0](rt)
            if isinstance(usage, Usage):
                usage.track(event)

        return athunk


def is_system(plane_id: nu.StrArg) -> nu.Bool:
    """Whether ``plane_id`` is a system plane. Bare read."""
    return nu.bool(Space.planes[plane_id].props.system.fallback(False))


def _changed_id(key: nu.ObjectRef) -> nu.Str:
    """The id a change names: the last part of the path it hears, eg ``("/", "planes", id)``."""
    return nu.Str(nu.list(key)[-1])


def _plane_changed(key: nu.ObjectRef) -> nu.Nu:
    """A plane id came or went: made unless a system plane, or removed (a system one never is)."""
    pid = _changed_id(key)
    made = nu.IfDo(snap(is_system(pid).not_()), Track("plane_created"))
    return nu.IfDo(snap(plane_exists(pid)), made, Track("plane_removed"))


def _cell_changed(key: nu.ObjectRef) -> nu.Nu:
    """A cell id came or went: made unless on a system plane, or removed."""
    cid = _changed_id(key)
    on_system = is_system(Space.cells[cid].plane.fallback(""))
    made = nu.IfDo(snap(on_system.not_()), Track("cell_created"))
    return nu.IfDo(snap(cell_exists(cid)), made, Track("cell_removed"))


def watch() -> nu.Nu:
    """Planes and cells made and removed, told per changed id, while a :class:`Usage` is bound.

    O(1) per change: the change names the id, and one read says whether it
    is there and whose. Edits inside a plane or a cell are deeper writes and
    wake nothing. Never returns once bound. Never raises either: a change
    that fails to read is skipped, and a watch that cannot start ends, so
    usage never takes the kernel down with it.
    """

    def heard(changed: Callable[[nu.ObjectRef], nu.Nu]) -> Callable[[nu.ObjectRef], nu.Nu]:
        return lambda key: nu.TryCatch(changed(key), catch=lambda _: nu.Noop())

    arms = nu.ParallelAsync(
        nu.ReactForever(snap(Space.planes.on_children_change()), heard(_plane_changed)),
        nu.ReactForever(snap(Space.cells.on_children_change()), heard(_cell_changed)),
    )
    return nu.IfDo(UsageRef().exists(), nu.TryCatch(arms, catch=lambda _: nu.Noop()))
