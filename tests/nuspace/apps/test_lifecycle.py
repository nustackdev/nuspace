"""The apps runner end to end: real processes, real RocksDB, no mocks.

Every assertion is about something the runner actually did -- a worker id it
recorded, a kv write an app made from inside its own process -- and every
observation is taken by a Nu term running inside the one tree, because
``Runner.workers`` is mem in the host process and does not outlive the run.
"""

from __future__ import annotations

import multiprocessing

import pytest

import nu
from nuspace.apps import ops, run_apps

from .conftest import (
    BROKEN,
    NONE,
    UNWRAPPED,
    read_state,
    seed_store,
    seq,
    snap,
    snap_ticks,
    write_app,
)


pytestmark = pytest.mark.timeout(300)

#: A reconcile is a process spawn, and a live write costs several of them
#: (the change feed is per field, and the row itself is a change too), so
#: the waits here are long on purpose. Shortening them buys flakiness.
SETTLE = 4.0


async def test_an_app_already_in_the_store_is_launched_and_runs(store):
    """The seed pass: apps present at boot get a worker and their writes land."""
    await seed_store(store, {"a_one": None, "a_two": None})

    await run_apps(
        store,
        alongside=nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two")),
        duration=SETTLE + 2.0,
    )

    state = await read_state(store)
    assert int(state["apps.a_one.ticks"]) > 0
    assert int(state["apps.a_two.ticks"]) > 0
    assert state["probe.t1.a_one"] != NONE
    assert state["probe.t1.a_two"] != NONE
    assert state["probe.t1.a_one"] != state["probe.t1.a_two"]


async def test_adding_an_app_live_does_not_disturb_the_running_ones(store):
    """A new app starts; the workers already running are not touched."""
    await seed_store(store, {"a_one": None, "a_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two"))
        >> nu.DelayedDo(0.2, write_app("a_new"))
        >> nu.DelayedDo(SETTLE, snap("t2", "a_one", "a_two", "a_new"))
    )
    await run_apps(store, alongside=script, duration=2 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t2.a_new"] != NONE
    assert int(state["apps.a_new.ticks"]) > 0
    assert state["probe.t2.a_one"] == state["probe.t1.a_one"]
    assert state["probe.t2.a_two"] == state["probe.t1.a_two"]


async def test_editing_a_snippet_restarts_only_that_app(store):
    """One edit, one restart. The other app's worker id does not move."""
    await seed_store(store, {"a_one": None, "a_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two"))
        >> nu.DelayedDo(0.2, write_app("a_one"))
        >> nu.DelayedDo(SETTLE, snap("t2", "a_one", "a_two"))
    )
    await run_apps(store, alongside=script, duration=2 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t2.a_one"] != state["probe.t1.a_one"]
    assert state["probe.t2.a_one"] != NONE
    assert state["probe.t2.a_two"] == state["probe.t1.a_two"]


async def test_deleting_an_app_kills_its_worker_and_forgets_it(store):
    """The app leaves ``Runner.workers``, its process stops, the rest carry on."""
    await seed_store(store, {"a_one": None, "a_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two"))
        >> nu.DelayedDo(0.2, ops.remove_app("a_two"))
        >> nu.DelayedDo(
            SETTLE, seq(snap("t2", "a_one", "a_two"), snap_ticks("t2", "a_one", "a_two"))
        )
        >> nu.DelayedDo(
            SETTLE, seq(snap("t3", "a_one", "a_two"), snap_ticks("t3", "a_one", "a_two"))
        )
    )
    await run_apps(store, alongside=script, duration=3 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t1.a_two"] != NONE
    assert state["probe.t2.a_two"] == NONE
    assert state["probe.t3.a_two"] == NONE
    # Its process really stopped: the counter it owned froze.
    assert state["probe.t3.a_two.ticks"] == state["probe.t2.a_two.ticks"]
    # The other app was not disturbed and is still counting.
    assert state["probe.t2.a_one"] == state["probe.t1.a_one"]
    assert int(state["probe.t3.a_one.ticks"]) > int(state["probe.t2.a_one.ticks"])


async def test_teardown_reaps_every_worker(store):
    """Bracket close kills the fleet; nothing is left behind."""
    await seed_store(store, {"a_one": None, "a_two": None, "a_three": None})

    await run_apps(store, duration=SETTLE)

    assert multiprocessing.active_children() == []


async def test_a_snippet_that_does_not_wrap_its_writes_fails(store):
    """The runner brackets its own read of the snippet and nothing else.

    Pinned rather than fixed: a snippet owns its atomicity, so an unwrapped
    kv write has no snapshot to land in. The app is launched and dispatched
    all the same -- it just dies inside its worker -- which is why the only
    visible evidence is that the write never landed.
    """
    await seed_store(store, {"a_bare": UNWRAPPED, "a_ok": None})

    await run_apps(
        store,
        alongside=nu.DelayedDo(SETTLE, snap("t1", "a_bare", "a_ok")),
        duration=SETTLE + 2.0,
    )

    state = await read_state(store)
    assert state["probe.t1.a_bare"] != NONE, "it was launched"
    assert "apps.a_bare.ticks" not in state, "but its unwrapped write never landed"
    assert int(state["apps.a_ok.ticks"]) > 0


async def test_a_snippet_that_does_not_construct_reports_itself(store):
    """A construction failure is written down, not dropped.

    A dispatched body has no waiter, so an uncaught error in one vanishes
    with nothing anywhere saying so. ``app_body`` catches ``ConstructionError``
    and lands it under the app's own namespace instead.
    """
    await seed_store(store, {"a_broken": BROKEN, "a_ok": None})

    await run_apps(store, duration=SETTLE)

    state = await read_state(store)
    assert "apps.a_broken.error" in state
    assert int(state["apps.a_ok.ticks"]) > 0
