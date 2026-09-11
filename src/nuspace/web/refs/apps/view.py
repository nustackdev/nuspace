"""One connection's view of the Apps surface.

A ``View`` is what the interactions in ``interactions/`` are written
against. It is per connection and dies with it -- but what it holds is
the structural difference between this surface and Pages.

## Observation, not ownership

``pages.View`` owns a supervisor. This one does not, and cannot: an app
runs whether or not a browser is looking, so its supervisor lives at
space lifetime in the app tree (``runtime.py`` / ``runner.py``) and this
View merely **observes** it.

Two halves, and they are the two runtime interactions:

- ``observe`` resolves the live runtime and moves this connection's
  status listener onto it. It is re-resolved on every use rather than
  captured once, because a browser can connect before the runner has
  published, and because a restarted runner publishes a *different*
  runtime under the same root.
- ``wake`` asks that runtime to reconcile now rather than at its next
  poll, which is what makes an edit from the browser feel instant.

``AppsRuntime.on_change`` is a plain python callback list, so attaching
is an append and detaching is a remove. That is why ``dispose`` has to
run: the runtime outlives the connection and would otherwise keep calling
into a dead one. Every other teardown on this surface is nu's.

## No cursor

Pages keeps one, because the server has to know which page to ship.
Apps ships the whole list to everybody, so the selected app is purely a
browser concern and never reaches python.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
from nu.kv.tree import auto_flow_atomic
from nuspace.web.refs.apps.runtime import get_runtime
from nuspace.web.refs.apps.store import app_row, ordered_apps
from nuspace.web.refs.common import Dirty, StatusRelay


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.lang import Context
    from nuspace.web.refs.apps.runtime import AppsRuntime


__all__ = ["View"]


class View:
    """Per-connection state the Apps interactions read and write."""

    def __init__(self, ctx: Context, root: type[Shape]) -> None:
        self.ctx = ctx
        self.root = root
        self.apps_dirty = Dirty()
        self.status = StatusRelay()
        # Held once rather than rebound per call: `off_change` removes by
        # equality, and one object is easier to reason about than trusting
        # bound-method comparison.
        self._listener = self.status.push
        self._observed: AppsRuntime | None = None
        self._last_apps: dict[str, Any] | None = None

    # -- evaluation ----------------------------------------------------------

    async def run(self, term: nu.Nu) -> Any:  # noqa: ANN401 -- kv values are opaque
        """Evaluate one Nu term against this space's storage."""
        value, _ = await nu.arun(auto_flow_atomic(term, scope=self.root), self.ctx)  # type: ignore[arg-type]
        return value

    async def write(self, term: nu.Nu) -> None:
        """Evaluate a term for its effect and drop the value."""
        await self.run(term)

    async def read(self, term: nu.Nu, default: Any = None) -> Any:  # noqa: ANN401
        """Evaluate a term, answering ``default`` if the read blows up.

        A slot that was never written reads back as a Nu sentinel and an
        address through a missing container raises. Neither is worth a
        traceback on a surface whose whole job is to paint what is there.
        """
        try:
            return await self.run(term)
        except Exception:
            return default

    # -- the runtime ---------------------------------------------------------

    def observe(self) -> AppsRuntime | None:
        """Resolve the live runtime, moving our status listener if it changed.

        None means no ``AppsRunner`` is mounted. That is shipped as
        ``attached: false`` rather than being papered over.
        """
        live = get_runtime(self.root)
        if live is self._observed:
            return live
        if self._observed is not None:
            self._observed.off_change(self._listener)
        if live is not None:
            live.on_change(self._listener)
        self._observed = live
        return live

    def wake(self) -> None:
        """Ask the supervisor to reconcile now rather than at the next poll."""
        live = self.observe()
        if live is not None:
            live.wake()

    # -- invalidation --------------------------------------------------------

    async def invalidate(self, key: object = None) -> None:
        """Mark the app list stale. Called per kv notification.

        The body only marks; the loop does the reading. Notifications are
        per key rather than per logical op -- one ``set_item`` on an app
        fires one per slot -- and a body that shipped would ship each
        time. ``key`` is the full absolute kv key and is here for whoever
        wants to get cleverer about it.
        """
        del key
        self.apps_dirty.mark()

    # -- payloads ------------------------------------------------------------

    async def next_apps(self) -> dict[str, Any]:
        """Wait until the app list has something new to say, then say it.

        Two filters, and both earn their keep. Time coalesces a burst
        into one read; value drops a read that came back identical and
        loops back to waiting rather than shipping a frame the browser
        would apply over itself.
        """
        while True:
            await self.apps_dirty.settled()
            payload = await self.apps_payload()
            if payload != self._last_apps:
                self._last_apps = payload
                return payload

    async def apps_payload(self) -> dict[str, Any]:
        """Build the app list payload now, status included."""
        live = self.observe()
        raw = await self.read(self.root.apps.extract())
        apps = [
            app_row(aid, blob, live.status(aid) if live is not None else None)
            for aid, blob in ordered_apps(raw)
        ]
        return {"op": "set_apps", "apps": apps, "attached": live is not None}

    async def next_status(self) -> dict[str, Any]:
        """Wait for the next status burst, return it as one frame."""
        return {"op": "set_status", "statuses": await self.status.batch()}

    # -- lifecycle -----------------------------------------------------------

    async def dispose(self) -> None:
        """Detach this connection's listener. Supervision is unaffected."""
        if self._observed is not None:
            self._observed.off_change(self._listener)
            self._observed = None
