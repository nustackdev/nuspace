"""One page's driver end to end: real processes, real RocksDB, no mocks.

Every assertion is about something the driver actually did -- a worker id it
recorded, a kv write a section made from inside its own process -- and every
observation is taken by a Nu term running inside the one tree, because
``Runner.workers`` is mem in the host process and does not outlive the run.

The host here is the test's, not the runner's: ``page_tree`` brings no store
and no pool, so ``run_page`` in the conftest stands in for the preset.
"""

from __future__ import annotations

import multiprocessing

import pytest

import nu
from nuspace.pages import ops

from .conftest import (
    BROKEN,
    COUNTER,
    NONE,
    read_state,
    run_page,
    seed_pages,
    seed_store,
    seq,
    snap,
    snap_ticks,
)


pytestmark = pytest.mark.timeout(300)

#: A reconcile is a process spawn, and a live write costs several of them
#: (the change feed is per field, and the row itself is a change too), so
#: the waits here are long on purpose. Shortening them buys flakiness.
SETTLE = 4.0

PAGE = "guides"

#: An edit has to be a real byte change or the store writes nothing at all.
EDITED = COUNTER + "\n# edited\n"


async def test_a_section_already_on_the_page_is_launched_and_runs(store):
    """The seed pass: sections present at boot get a worker and their writes land."""
    await seed_store(store, PAGE, {"s_one": None, "s_two": None})

    await run_page(
        store,
        PAGE,
        alongside=nu.DelayedDo(SETTLE, snap("t1", "s_one", "s_two")),
        duration=SETTLE + 2.0,
    )

    state = await read_state(store)
    assert int(state["sections.s_one.ticks"]) > 0
    assert int(state["sections.s_two.ticks"]) > 0
    assert state["probe.t1.s_one"] != NONE
    assert state["probe.t1.s_two"] != NONE
    assert state["probe.t1.s_one"] != state["probe.t1.s_two"]


async def test_a_section_on_another_page_is_left_alone(store):
    """The driver is scoped to one page: a sibling page's sections never run."""
    await seed_store(store, PAGE, {"s_mine": None})
    await seed_store(store, "other", {"s_theirs": None})

    await run_page(store, PAGE, duration=SETTLE)

    state = await read_state(store)
    assert int(state["sections.s_mine.ticks"]) > 0
    assert "sections.s_theirs.ticks" not in state


async def test_adding_a_section_live_does_not_disturb_the_running_ones(store):
    """A new section starts; the workers already running are not touched."""
    await seed_store(store, PAGE, {"s_one": None, "s_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "s_one", "s_two"))
        >> nu.DelayedDo(0.2, ops.add_section(PAGE, EDITED, section_id="s_new"))
        >> nu.DelayedDo(SETTLE, snap("t2", "s_one", "s_two", "s_new"))
    )
    await run_page(store, PAGE, alongside=script, duration=2 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t2.s_new"] != NONE
    assert int(state["sections.s_new.ticks"]) > 0
    assert state["probe.t2.s_one"] == state["probe.t1.s_one"]
    assert state["probe.t2.s_two"] == state["probe.t1.s_two"]


async def test_creating_a_section_costs_exactly_one_launch(store):
    """The real write pattern -- every field at once -- must still cost one worker.

    ``add_section`` writes order, name, policy, tpl and snippet, and the
    subscription behind the driver is depth-unbounded, so this wakes reconcile
    five to eight times. Pool ids are monotonic from zero and never reused, so
    a recorded id of 0 is the whole assertion: one launch, ever.
    """
    await seed_pages(store, PAGE)

    script = (
        nu.DelayedDo(
            1.0,
            ops.add_section(
                PAGE, COUNTER, section_id="s_new", name="New", tpl="program", policy="always"
            ),
        )
        >> nu.DelayedDo(SETTLE, seq(snap("t1", "s_new"), snap_ticks("t1", "s_new")))
        >> nu.DelayedDo(SETTLE, seq(snap("t2", "s_new"), snap_ticks("t2", "s_new")))
    )
    await run_page(store, PAGE, alongside=script, duration=2 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t1.s_new"] == "0"
    # And it is the same worker later, still alive and still counting.
    assert state["probe.t2.s_new"] == "0"
    assert int(state["probe.t2.s_new.ticks"]) > int(state["probe.t1.s_new.ticks"])
    assert multiprocessing.active_children() == []


async def test_writing_a_field_other_than_the_snippet_restarts_nothing(store):
    """A rename or a tpl change is not an edit. The worker must not move."""
    await seed_store(store, PAGE, {"s_one": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "s_one"))
        >> nu.DelayedDo(0.2, ops.set_tpl(PAGE, "s_one", "notebook"))
        >> nu.DelayedDo(SETTLE, seq(snap("t2", "s_one"), snap_ticks("t2", "s_one")))
        >> nu.DelayedDo(SETTLE, snap_ticks("t3", "s_one"))
    )
    await run_page(store, PAGE, alongside=script, duration=3 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t1.s_one"] != NONE
    assert state["probe.t2.s_one"] == state["probe.t1.s_one"]
    assert int(state["probe.t3.s_one.ticks"]) > int(state["probe.t2.s_one.ticks"])


async def test_editing_a_snippet_restarts_only_that_section(store):
    """One edit, one restart. The other section's worker id does not move."""
    await seed_store(store, PAGE, {"s_one": None, "s_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "s_one", "s_two"))
        >> nu.DelayedDo(0.2, ops.set_snippet(PAGE, "s_one", EDITED))
        >> nu.DelayedDo(SETTLE, snap("t2", "s_one", "s_two"))
    )
    await run_page(store, PAGE, alongside=script, duration=2 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t2.s_one"] != state["probe.t1.s_one"]
    assert state["probe.t2.s_one"] != NONE
    assert state["probe.t2.s_two"] == state["probe.t1.s_two"]


async def test_deleting_a_section_kills_its_worker_and_forgets_it(store):
    """The section leaves ``Runner.workers``, its process stops, the rest carry on."""
    await seed_store(store, PAGE, {"s_one": None, "s_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "s_one", "s_two"))
        >> nu.DelayedDo(0.2, ops.remove_section(PAGE, "s_two"))
        >> nu.DelayedDo(
            SETTLE, seq(snap("t2", "s_one", "s_two"), snap_ticks("t2", "s_one", "s_two"))
        )
        >> nu.DelayedDo(
            SETTLE, seq(snap("t3", "s_one", "s_two"), snap_ticks("t3", "s_one", "s_two"))
        )
    )
    await run_page(store, PAGE, alongside=script, duration=3 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t1.s_two"] != NONE
    assert state["probe.t2.s_two"] == NONE
    assert state["probe.t3.s_two"] == NONE
    # Its process really stopped: the counter it owned froze.
    assert state["probe.t3.s_two.ticks"] == state["probe.t2.s_two.ticks"]
    # The other section was not disturbed and is still counting.
    assert state["probe.t2.s_one"] == state["probe.t1.s_one"]
    assert int(state["probe.t3.s_one.ticks"]) > int(state["probe.t2.s_one.ticks"])


async def test_removing_the_page_stops_every_section_on_it(store):
    """A page is a container, so dropping it is a delete for each of its sections."""
    await seed_store(store, PAGE, {"s_one": None, "s_two": None})

    script = (
        nu.DelayedDo(SETTLE, snap("t1", "s_one", "s_two"))
        >> nu.DelayedDo(0.2, ops.remove_page(PAGE))
        >> nu.DelayedDo(SETTLE, snap("t2", "s_one", "s_two"))
    )
    await run_page(store, PAGE, alongside=script, duration=2 * SETTLE + 4.0)

    state = await read_state(store)
    assert state["probe.t1.s_one"] != NONE
    assert state["probe.t2.s_one"] == NONE
    assert state["probe.t2.s_two"] == NONE


async def test_teardown_reaps_every_worker(store):
    """Bracket close kills the fleet; nothing is left behind."""
    await seed_store(store, PAGE, {"s_one": None, "s_two": None, "s_three": None})

    await run_page(store, PAGE, duration=SETTLE)

    assert multiprocessing.active_children() == []


async def test_a_snippet_that_does_not_construct_reports_itself(store):
    """A construction failure is written down, not dropped.

    A dispatched body has no waiter, so an uncaught error in one vanishes with
    nothing anywhere saying so. ``section_body`` catches ``ConstructionError``
    and lands it under the section's own namespace instead.
    """
    await seed_store(store, PAGE, {"s_broken": BROKEN, "s_ok": None})

    await run_page(store, PAGE, duration=SETTLE)

    state = await read_state(store)
    assert "sections.s_broken.error" in state
    assert int(state["sections.s_ok.ticks"]) > 0
