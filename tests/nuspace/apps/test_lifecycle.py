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
    COUNTER,
    NONE,
    UNWRAPPED,
    read_data,
    read_error,
    read_probes,
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

#: An edit has to be a real change to the source, or reconcile reads the app
#: as already running exactly that and leaves the worker where it is.
EDITED = COUNTER + "\n# edited\n"


async def test_an_app_already_in_the_store_is_launched_and_runs(store):
    """The seed pass: apps present at boot get a worker and their writes land."""
    await seed_store(store, {"a_one": None, "a_two": None})

    await run_apps(
        store,
        alongside=nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two")),
        duration=SETTLE + 2.0,
    )

    probes = await read_probes(store)
    assert int((await read_data(store, "a_one"))["ticks"]) > 0
    assert int((await read_data(store, "a_two"))["ticks"]) > 0
    assert probes["t1.a_one"] != NONE
    assert probes["t1.a_two"] != NONE
    assert probes["t1.a_one"] != probes["t1.a_two"]


async def test_adding_an_app_live_does_not_disturb_the_running_ones(store):
    """A new app starts; the workers already running are not touched."""
    await seed_store(store, {"a_one": None, "a_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two"))
        >> nu.DelayedDo(0.2, write_app("a_new"))
        >> nu.DelayedDo(SETTLE, snap("t2", "a_one", "a_two", "a_new"))
    )
    await run_apps(store, alongside=script, duration=2 * SETTLE + 4.0)

    probes = await read_probes(store)
    assert probes["t2.a_new"] != NONE
    assert int((await read_data(store, "a_new"))["ticks"]) > 0
    assert probes["t2.a_one"] == probes["t1.a_one"]
    assert probes["t2.a_two"] == probes["t1.a_two"]


async def test_creating_an_app_costs_exactly_one_launch(store):
    """The real write pattern -- every field at once -- must still cost one worker.

    ``add_app`` writes name, policy and snippet, and the subscription behind
    the runner is depth-unbounded, so this wakes reconcile several times over.
    Pool ids are monotonic from zero and never reused, so a recorded id of 0
    is the whole assertion: one launch, ever.
    """
    script = (
        nu.DelayedDo(1.0, ops.add_app(COUNTER, app_id="a_new", name="New"))
        >> nu.DelayedDo(SETTLE, seq(snap("t1", "a_new"), snap_ticks("t1", "a_new")))
        >> nu.DelayedDo(SETTLE, seq(snap("t2", "a_new"), snap_ticks("t2", "a_new")))
    )
    await run_apps(store, alongside=script, duration=2 * SETTLE + 4.0)

    probes = await read_probes(store)
    assert probes["t1.a_new"] == "0"
    # And it is the same worker later, still alive and still counting.
    assert probes["t2.a_new"] == "0"
    assert int(probes["t2.a_new.ticks"]) > int(probes["t1.a_new.ticks"])
    assert multiprocessing.active_children() == []


async def test_renaming_an_app_restarts_nothing(store):
    """A rename is not an edit. The worker must not move."""
    await seed_store(store, {"a_one": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "a_one"))
        >> nu.DelayedDo(0.2, ops.rename_app("a_one", "Renamed"))
        >> nu.DelayedDo(SETTLE, seq(snap("t2", "a_one"), snap_ticks("t2", "a_one")))
        >> nu.DelayedDo(SETTLE, snap_ticks("t3", "a_one"))
    )
    await run_apps(store, alongside=script, duration=3 * SETTLE + 4.0)

    probes = await read_probes(store)
    assert probes["t1.a_one"] != NONE
    assert probes["t2.a_one"] == probes["t1.a_one"]
    assert int(probes["t3.a_one.ticks"]) > int(probes["t2.a_one.ticks"])


async def test_editing_a_snippet_restarts_only_that_app(store):
    """One edit, one restart. The other app's worker id does not move."""
    await seed_store(store, {"a_one": None, "a_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "a_one", "a_two"))
        >> nu.DelayedDo(0.2, write_app("a_one", EDITED))
        >> nu.DelayedDo(SETTLE, snap("t2", "a_one", "a_two"))
    )
    await run_apps(store, alongside=script, duration=2 * SETTLE + 4.0)

    probes = await read_probes(store)
    assert probes["t2.a_one"] != probes["t1.a_one"]
    assert probes["t2.a_one"] != NONE
    assert probes["t2.a_two"] == probes["t1.a_two"]


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

    probes = await read_probes(store)
    assert probes["t1.a_two"] != NONE
    assert probes["t2.a_two"] == NONE
    assert probes["t3.a_two"] == NONE
    # Its process really stopped: the counter it owned froze.
    assert probes["t3.a_two.ticks"] == probes["t2.a_two.ticks"]
    # The other app was not disturbed and is still counting.
    assert probes["t2.a_one"] == probes["t1.a_one"]
    assert int(probes["t3.a_one.ticks"]) > int(probes["t2.a_one.ticks"])


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

    probes = await read_probes(store)
    assert probes["t1.a_bare"] != NONE, "it was launched"
    assert await read_data(store, "a_bare") == {}, "but its unwrapped write never landed"
    assert int((await read_data(store, "a_ok"))["ticks"]) > 0


async def test_a_snippet_that_does_not_construct_reports_itself(store):
    """A construction failure is written down, not dropped.

    A dispatched body has no waiter, so an uncaught error in one vanishes
    with nothing anywhere saying so. ``app_body`` catches ``ConstructionError``
    and lands it on the app's own row instead.
    """
    await seed_store(store, {"a_broken": BROKEN, "a_ok": None})

    await run_apps(store, duration=SETTLE)

    assert await read_error(store, "a_broken") != ""
    assert int((await read_data(store, "a_ok"))["ticks"]) > 0
