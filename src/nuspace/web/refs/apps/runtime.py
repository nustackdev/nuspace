"""``AppsRuntime`` -- the apps supervisor, at **space** lifetime.

This is the structural difference between the two pillars, and it is
most of what this module exists to get right.

Pages' supervisor is per connection. A driver spawns when a browser
connects, sections run while a page is open, and everything dies on
disconnect. That is correct for ui orchestration: nobody is looking, so
nothing needs to be drawn.

"Always" is not that. An app produces; it runs whether or not a browser
is attached. So the supervisor cannot live in the connection's driver.
It lives here, is created once by :class:`~nuspace.web.refs.apps.runner.AppsRunner`
mounted in the **space's own tree**, and it outlives every connection.
The ``AppsRef`` driver then *observes* it and never owns it.

Consequences, which are the acceptance criteria:

- Boot the space with no browser: the runner starts, apps run.
- Connect a browser mid-run: the driver reads ``statuses()`` and paints
  what is already running. It starts nothing.
- Connect a second browser: it finds the same runtime under the same
  root, so both see one set of apps rather than one set each.
- Reload: the connection dies, the runtime does not.

## Finding the runtime

One process runs one space, so the registry is keyed by the root Shape
class rather than being a bare module global. That is not ceremony: the
test suite runs several spaces in one interpreter, and a subclassed root
(``DemoSpace(Space)``) is a genuinely different space with genuinely
different kv addresses.

## Reconcile

The loop reads ``root.apps``, hands the list to the supervisor, and
launches whatever the supervisor decided is new or edited. It then
sleeps until either ``POLL_S`` elapses or someone calls :meth:`wake`.

Polling *and* waking, on purpose. ``wake`` is what makes an edit from
the browser feel instant -- the driver writes kv and rings the bell. The
poll is what makes every other writer work: model.md says an app may add
another app, and a kv write from a proxy client, a script or another app
has nobody to ring the bell for it. nu has no deep-wildcard reactive
subscription, so a bounded poll over a flat list of apps is the honest
floor, not a stopgap.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import nu
from nu.kv.tree import auto_flow_atomic

from .store import MAX_APPS
from .supervise import AppSpec, AppsSupervisor


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape


__all__ = [
    "MAX_APPS",
    "POLL_S",
    "AppsRuntime",
    "get_runtime",
    "install_runtime",
]


# Reconcile floor. An edit does not wait for this -- `wake()` short-circuits
# it -- so this only bounds how stale a write nuspace did not make can get.
POLL_S = 1.0


class AppsRuntime:
    """Supervises every app in one space, for the life of that space."""

    def __init__(self, ctx: object, root: type[Shape]) -> None:
        self._ctx = ctx
        self._root = root
        self._supervisor = AppsSupervisor(ctx, root)
        self._wake = asyncio.Event()
        self._listeners: list[Callable[[dict[str, Any]], None]] = []
        self._supervisor.on_change(self._fanout)
        self.generation = 0

    # -- observation ---------------------------------------------------------

    def on_change(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """Register a status observer. Drivers add one each and drop it on close."""
        self._listeners.append(cb)

    def off_change(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """Drop an observer. Idempotent, because teardown paths run twice."""
        with contextlib.suppress(ValueError):
            self._listeners.remove(cb)

    def _fanout(self, wire: dict[str, Any]) -> None:
        for cb in list(self._listeners):
            try:
                cb(wire)
            except Exception:  # noqa: S110 -- one dead connection must not stop supervision
                pass

    def statuses(self) -> list[dict[str, Any]]:
        """Every known app's status, wire-shaped. What a joining browser paints."""
        return self._supervisor.statuses()

    def status(self, app_id: str) -> dict[str, Any]:
        """One app's status. Unknown ids read as ``idle``."""
        return self._supervisor.status(app_id)

    # -- driving -------------------------------------------------------------

    def wake(self) -> None:
        """Reconcile now rather than at the next poll. Safe from any task."""
        self._wake.set()

    async def restart(self, app_id: str) -> None:
        """Restart one app from its current source. Neighbours are untouched."""
        await self._supervisor.restart(app_id)

    async def read_specs(self) -> list[AppSpec]:
        """Read ``root.apps`` out of kv into supervisor specs."""
        term = auto_flow_atomic(self._root.apps.extract(), scope=self._root)
        try:
            raw, _ = await nu.arun(term, self._ctx)  # type: ignore[arg-type]
        except Exception:
            return []
        if not isinstance(raw, dict):
            return []
        specs: list[AppSpec] = []
        for aid, blob in sorted(raw.items())[:MAX_APPS]:
            if not isinstance(blob, dict):
                continue
            specs.append(AppSpec(str(aid), str(blob.get("snippet") or "")))
        return specs

    async def reconcile(self) -> None:
        """One pass: read kv, plan, launch what plan left pending."""
        specs = await self.read_specs()
        self._supervisor.plan(list(specs))
        await self._supervisor.launch()
        self.generation += 1

    async def arun(self) -> None:
        """The reconcile loop. Runs until cancelled, i.e. until the space ends."""
        try:
            while True:
                await self.reconcile()
                self._wake.clear()
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._wake.wait(), timeout=POLL_S)
        finally:
            await self._supervisor.stop_all()


# -- registry ----------------------------------------------------------------

_RUNTIMES: dict[type, AppsRuntime] = {}


def get_runtime(root: type[Shape]) -> AppsRuntime | None:
    """The runtime supervising ``root``'s apps, or None if no runner is mounted.

    None is a real, renderable answer: the space is up and its apps are
    simply not being supervised. The Apps surface says so rather than
    lying about a list of idle apps.
    """
    return _RUNTIMES.get(root)


@contextlib.contextmanager
def install_runtime(root: type[Shape], runtime: AppsRuntime) -> Any:  # noqa: ANN401
    """Publish ``runtime`` for ``root`` for the duration of the block.

    Last writer wins and the previous entry is restored on exit, so a
    test that mounts a second runner over the same root cannot leave a
    dead runtime behind for the next test to find.
    """
    previous = _RUNTIMES.get(root)
    _RUNTIMES[root] = runtime
    try:
        yield runtime
    finally:
        if _RUNTIMES.get(root) is runtime:
            if previous is None:
                _RUNTIMES.pop(root, None)
            else:
                _RUNTIMES[root] = previous
