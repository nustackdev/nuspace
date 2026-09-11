"""Coalescing: two small objects that stand between a burst and a frame.

Notifications are per key, not per logical op. Deleting a page with four
sections fires eleven kv notifications; creating one fires three. A
supervisor moving a section from starting to running fires twice within a
tick. Shipping a frame per notification is correct and unusable.

Both objects have the same shape: mark from anywhere, await a settled
edge, ship once. Neither knows what it is coalescing.
"""

from __future__ import annotations

import asyncio
from typing import Any


__all__ = ["Dirty", "StatusRelay"]

# A burst lands well inside a tick; anything longer is a different event.
FLUSH_S = 0.03


class Dirty:
    """A debounced flag: mark it from anywhere, await its settled edge.

    ``mark`` is sync and never blocks, so it is safe to call from a kv
    notification. ``settled`` waits for the first mark, sleeps out the
    window, and clears -- so every mark that lands inside the window is
    absorbed into the one flush. There is no await between the sleep and
    the clear, so a mark cannot be lost in the gap.
    """

    def __init__(self, window: float = FLUSH_S) -> None:
        self._event = asyncio.Event()
        self._window = window

    def mark(self) -> None:
        """Say something changed. Cheap, sync, idempotent inside a window."""
        self._event.set()

    async def settled(self) -> None:
        """Block until marked, then until the burst stops arriving."""
        await self._event.wait()
        await asyncio.sleep(self._window)
        self._event.clear()


class StatusRelay:
    """Queue of section status wires, drained one batch at a time.

    Same debounce as ``Dirty`` with one addition: the batch is keyed by
    ``section_id``, so a section that goes starting then running inside
    one window ships as running only.
    """

    def __init__(self, window: float = FLUSH_S) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._window = window
        self._loop = asyncio.get_running_loop()

    def push(self, wire: dict[str, Any]) -> None:
        """Record one status change.

        Supervision emits from whatever task -- or thread -- the section
        runs on, so this hops to the loop rather than touching the queue
        where it stands.
        """
        self._loop.call_soon_threadsafe(self._queue.put_nowait, wire)

    async def batch(self) -> list[dict[str, Any]]:
        """Block for the next burst, return one status per section."""
        first = await self._queue.get()
        batch: dict[str, dict[str, Any]] = {first["section_id"]: first}
        await asyncio.sleep(self._window)
        while not self._queue.empty():
            item = self._queue.get_nowait()
            batch[item["section_id"]] = item
        return list(batch.values())
