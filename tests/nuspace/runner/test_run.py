"""End to end: seed apps, run them, check what landed in the store.

These are the tests that actually spawn processes and open a RocksDB, so
they are slower than the rest and they are the only ones exercising
``nu.proxy`` at all.
"""

from __future__ import annotations

import asyncio
import multiprocessing

import pytest

import nu
import nu.kv
from nuspace.core.shapes import Space
from nuspace.runner import demo_apps, free_port, launch, manifest, runner_tree, seed_store


pytestmark = pytest.mark.timeout(120)


async def read_state(path: str) -> dict:
    tree = nu.With(
        nu.kv.rocksdb_navigator(path, read_only=True),
        body=nu.kv.auto_flow_atomic(nu.dict(Space.state.items()), scope=Space),
    )
    rows, _ = await nu.arun(tree, nu.Context())
    return dict(rows or {})


async def test_manifest_reads_what_was_seeded(tmp_path):
    path = str(tmp_path / "db")
    await seed_store(path, demo_apps(2, ticks=1))
    assert await manifest(path) == ("a_00", "a_01", "a_mirror")


async def test_apps_run_and_their_writes_land(tmp_path):
    """Each app runs in its own process and writes through the proxy."""
    path = str(tmp_path / "db")
    await seed_store(path, demo_apps(2, ticks=3, every=0.02))

    slots = await launch(path, warm=1)

    assert [s.apps for s in slots] == [("a_00",), ("a_01",), ("a_mirror",)]
    state = await read_state(path)
    assert state["apps.a_00.ticks"] == "3"
    assert state["apps.a_01.ticks"] == "3"
    # The mirror read a_00's counter out of the store, from another process.
    assert "apps.a_mirror.seen" in state


async def test_the_pool_grows_when_the_apps_do_not_fit(tmp_path):
    path = str(tmp_path / "db")
    await seed_store(path, demo_apps(4, ticks=1, every=0.01))

    slots = await launch(path, warm=2)

    assert len(slots) == 5
    assert not multiprocessing.active_children()


async def test_batched_apps_share_one_worker(tmp_path):
    path = str(tmp_path / "db")
    await seed_store(path, demo_apps(3, ticks=2, every=0.02))

    slots = await launch(path, warm=1, per_worker=2)

    assert [s.apps for s in slots] == [("a_00", "a_01"), ("a_02", "a_mirror")]
    state = await read_state(path)
    assert state["apps.a_02.ticks"] == "2"


async def test_warm_workers_are_provisioned_with_nothing_to_do(tmp_path):
    """A warm worker is a live process holding a proxy, not a placeholder."""
    path = str(tmp_path / "db")
    await seed_store(path, {})

    seen: list[int] = []

    tree, slots = runner_tree(
        (),
        path=path,
        address=f"127.0.0.1:{free_port()}",
        warm=3,
        duration=0.2,
    )

    # The body is a Noop, so sample from outside the tree while it is up.
    async def watch() -> None:
        await asyncio.sleep(0.1)
        seen.append(len(multiprocessing.active_children()))

    watcher = asyncio.create_task(watch())
    await nu.arun(tree, nu.Context(), max_parallel=8)
    await watcher

    assert len(slots) == 3
    assert seen == [3]
    assert not multiprocessing.active_children()


async def test_a_second_writer_cannot_open_the_store(tmp_path):
    """Why the Navigator is served rather than opened per worker.

    RocksDB takes an exclusive directory lock. A second read-write open of
    the same directory does not degrade, it throws, and that holds across
    processes too, so the only way several processes share one store is
    through the proxy.
    """
    path = str(tmp_path / "db")
    await seed_store(path, {})

    outer = nu.With(nu.kv.rocksdb_navigator(path), body=nu.Noop())
    async with outer._aopen(nu.Context()):
        with pytest.raises(Exception):  # noqa: B017
            inner = nu.With(nu.kv.rocksdb_navigator(path), body=nu.Noop())
            async with inner._aopen(nu.Context()):
                pass
