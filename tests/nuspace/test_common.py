"""refs/common: the coalescing, and the op path a notify has to land on.

The stampede is the thing worth pinning. kv notifications are per key, not
per logical op: on the demo store a `page.create` fires 6 of them and
deleting a page with four blocks fires 28. Shipping one frame each is
correct and unusable, so `Dirty` and `StatusRelay` stand in between, and
a regression there is invisible until a rail flickers.
"""

from __future__ import annotations

import asyncio

from nuspace.web.refs.common import Dirty, OpRef, StatusRelay


# -- Dirty --------------------------------------------------------------------


async def test_a_burst_settles_into_one_flush():
    dirty = Dirty(window=0.02)
    flushes = 0

    async def loop() -> None:
        nonlocal flushes
        while True:
            await dirty.settled()
            flushes += 1

    task = asyncio.create_task(loop())
    for _ in range(28):
        dirty.mark()
        await asyncio.sleep(0)
    await asyncio.sleep(0.1)
    task.cancel()
    assert flushes == 1


async def test_a_mark_after_the_window_flushes_again():
    dirty = Dirty(window=0.01)
    flushes = 0

    async def loop() -> None:
        nonlocal flushes
        while True:
            await dirty.settled()
            flushes += 1

    task = asyncio.create_task(loop())
    dirty.mark()
    await asyncio.sleep(0.05)
    dirty.mark()
    await asyncio.sleep(0.05)
    task.cancel()
    assert flushes == 2


async def test_settled_blocks_until_marked():
    dirty = Dirty(window=0.01)
    done = asyncio.Event()

    async def wait() -> None:
        await dirty.settled()
        done.set()

    task = asyncio.create_task(wait())
    await asyncio.sleep(0.05)
    assert not done.is_set()
    dirty.mark()
    await asyncio.wait_for(done.wait(), timeout=1)
    task.cancel()


# -- StatusRelay --------------------------------------------------------------


async def test_a_batch_keeps_the_last_state_per_section():
    relay = StatusRelay(window=0.02)
    for state in ("starting", "running"):
        relay.push({"section_id": "s1", "state": state})
    relay.push({"section_id": "s2", "state": "failed"})
    batch = await asyncio.wait_for(relay.batch(), timeout=1)
    by_id = {w["section_id"]: w["state"] for w in batch}
    assert by_id == {"s1": "running", "s2": "failed"}


# -- op addresses -------------------------------------------------------------


def test_an_op_ref_is_the_surface_path_plus_the_op_name():
    # The browser builds the same string; the session dispatches a notify
    # by looking it up, so the two spellings have to agree exactly.
    ref = OpRef("DemoPagesPage.pages.ops.block.split")
    assert ref._payload["segment"] == "DemoPagesPage.pages.ops.block.split"
