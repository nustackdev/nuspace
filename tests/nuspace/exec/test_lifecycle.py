"""Process lifecycle: the kill guarantee, isolation, and generations.

Real processes throughout. The claim under test is that teardown is
bounded even when the section refuses to cooperate, and that is only
true if there is an actual signal at the end of the ladder.
"""

from __future__ import annotations

import asyncio
import os
import signal
import time

from nuspace.exec import SectionSpec, Supervisor


async def test_each_section_gets_its_own_worker(sup, src, settled):
    await sup.open_page("p1", [SectionSpec(f"s{i}", src.live) for i in range(4)])
    await settled(sup, "p1")
    pids = sup.pids("p1")
    assert len(pids) == 4
    assert len(set(pids.values())) == 4
    assert all(s["state"] == "running" for s in sup.status("p1").values())


async def test_wedged_section_dies_bounded_and_siblings_keep_running(
    sup, src, bounds, settled, alive, dead_within
):
    """A tree with no await point in it. Cancellation cannot reach it."""
    await sup.open_page(
        "p1",
        [
            SectionSpec("wedge", src.wedge_runtime),
            SectionSpec("live1", src.live),
            SectionSpec("live2", src.live),
        ],
    )
    await settled(sup, "p1", sections=["live1", "live2"])
    before = sup.pids("p1")

    await sup.update_section("p1", SectionSpec("wedge", src.live))
    await dead_within(before["wedge"], bounds.ladder + 1.0)

    after = sup.pids("p1")
    assert after["live1"] == before["live1"]
    assert after["live2"] == before["live2"]
    assert alive(after["live1"]) and alive(after["live2"])
    statuses = sup.status("p1")
    assert statuses["live1"]["state"] == "running"
    assert statuses["live2"]["state"] == "running"


async def test_section_wedged_in_compile_still_dies(sup, src, bounds, settled, dead_within):
    """Source that never returns from compilation. No tree ever exists."""
    await sup.open_page(
        "p1",
        [SectionSpec("wedge", src.wedge_compile), SectionSpec("live", src.live)],
    )
    await settled(sup, "p1", sections=["live"])
    wedge_pid = sup.pids("p1")["wedge"]
    assert sup.status("p1")["wedge"]["state"] == "starting"

    started = time.monotonic()
    await sup.close_page("p1")
    # Navigation is not allowed to wait on a process that will not die.
    assert time.monotonic() - started < 0.2
    await dead_within(wedge_pid, bounds.ladder + 1.0)


async def test_worker_ignoring_sigterm_is_killed(host, src, bounds, dead_within):
    """The full ladder: request, SIGTERM, SIGKILL. Only the last one lands."""
    sup = Supervisor(host, pool_size=1, timeouts=bounds.timeouts)
    await sup.astart()
    try:
        await sup.open_page("p1", [SectionSpec("nope", src.wedge_unkillable)])
        await asyncio.sleep(0.5)
        pid = sup.pids("p1")["nope"]
        handle = sup._pages["p1"].workers["nope"].handle
        started = time.monotonic()
        outcome = await handle.stop(bounds.timeouts)
        elapsed = time.monotonic() - started
        assert outcome == "kill"
        assert elapsed >= bounds.timeouts.graceful + bounds.timeouts.term
        assert elapsed < bounds.ladder + 1.0
        await dead_within(pid, 1.0)
    finally:
        await sup.aclose()


async def test_editing_one_section_restarts_only_that_section(
    sup, src, bounds, settled, dead_within
):
    await sup.open_page(
        "p1",
        [
            SectionSpec("a", src.live),
            SectionSpec("b", src.live),
            SectionSpec("c", src.live),
        ],
    )
    await settled(sup, "p1")
    before = sup.pids("p1")

    await sup.update_section("p1", SectionSpec("b", src.oneshot))
    await settled(sup, "p1", sections=["b"])
    after = sup.pids("p1")

    assert after["a"] == before["a"]
    assert after["c"] == before["c"]
    assert after["b"] != before["b"]
    await dead_within(before["b"], bounds.ladder + 1.0)
    assert sup.status("p1")["b"]["state"] == "stopped"
    assert sup.status("p1")["a"]["state"] == "running"
    assert sup.status("p1")["c"]["state"] == "running"


async def test_rapid_navigation_leaves_no_orphans(sup, src, alive):
    seen: set[int] = set()
    for i in range(6):
        page = f"p{i % 3}"
        await sup.open_page(
            page,
            [SectionSpec("x", src.ticker), SectionSpec("y", src.live)],
        )
        seen.update(sup.pids(page).values())
        await asyncio.sleep(0.02)

    for page in ("p0", "p1", "p2"):
        seen.update(sup.pids(page).values())
        await sup.close_page(page)
    await sup.drain()

    orphans = [pid for pid in seen if alive(pid)]
    assert orphans == [], f"orphaned workers: {orphans}"


async def test_navigation_never_overlaps_two_generations(sup, host, src, settled):
    await sup.open_page("p1", [SectionSpec("t", src.ticker)])
    await settled(sup, "p1")
    await asyncio.sleep(0.2)
    assert host.writes("sections.t.tick"), "ticker never wrote"

    gen1 = sup.generation("p1")
    await sup.open_page("p1", [SectionSpec("t", src.live)])
    assert sup.generation("p1") == gen1 + 1
    cut = len(host.frames)

    await asyncio.sleep(0.4)
    late = [f for _, _, f in host.frames[cut:] if f.ref == "sections.t.tick"]
    assert late == [], "a stale generation kept writing"


async def test_reopening_a_page_replaces_its_workers(sup, src, bounds, settled, dead_within):
    await sup.open_page("p1", [SectionSpec("a", src.live)])
    await settled(sup, "p1")
    old = sup.pids("p1")["a"]
    await sup.open_page("p1", [SectionSpec("a", src.live)])
    await settled(sup, "p1")
    assert sup.pids("p1")["a"] != old
    await dead_within(old, bounds.ladder + 1.0)


async def test_close_page_is_prompt_even_with_a_wedged_section(sup, src, settled):
    await sup.open_page(
        "p1",
        [SectionSpec("wedge", src.wedge_runtime), SectionSpec("live", src.live)],
    )
    await settled(sup, "p1", sections=["live"])
    started = time.monotonic()
    await sup.close_page("p1")
    assert time.monotonic() - started < 0.2
    assert sup.status("p1") == {}


async def test_failing_section_surfaces_failed_with_an_error(sup, src, settled):
    await sup.open_page(
        "p1",
        [SectionSpec("bad", src.raises), SectionSpec("good", src.live)],
    )
    await settled(sup, "p1")
    status = sup.status("p1")["bad"]
    assert status["state"] == "failed"
    assert "ZeroDivisionError" in status["error"]
    assert status["started_at"] is not None
    assert sup.status("p1")["good"]["state"] == "running"


async def test_uncompilable_section_is_invalid_and_the_page_survives(sup, src, settled):
    await sup.open_page(
        "p1",
        [SectionSpec("bad", src.syntax), SectionSpec("good", src.live)],
    )
    await settled(sup, "p1")
    status = sup.status("p1")["bad"]
    assert status["state"] == "invalid"
    assert "SyntaxError" in status["error"]
    assert "line 1" in status["error"]
    assert status["started_at"] is None
    assert sup.status("p1")["good"]["state"] == "running"


async def test_invalid_and_failed_are_distinct(sup, src, settled):
    await sup.open_page(
        "p1",
        [SectionSpec("never_ran", src.syntax), SectionSpec("ran_and_died", src.raises)],
    )
    await settled(sup, "p1")
    statuses = sup.status("p1")
    assert statuses["never_ran"]["state"] == "invalid"
    assert statuses["ran_and_died"]["state"] == "failed"


async def test_a_worker_killed_out_of_band_reports_failed(sup, src, settled):
    await sup.open_page("p1", [SectionSpec("s", src.live)])
    await settled(sup, "p1")
    os.kill(sup.pids("p1")["s"], signal.SIGKILL)
    await sup.wait_for("p1", {"failed"}, timeout=5.0)
    assert "worker exited" in sup.status("p1")["s"]["error"]


async def test_status_stream_reports_transitions(sup, src):
    sub = sup.stream.subscribe()
    try:
        await sup.open_page("p1", [SectionSpec("s", src.oneshot)])
        seen = []
        for _ in range(10):
            event = await sub.get(timeout=10.0)
            assert event.page_id == "p1"
            assert event.generation == 1
            seen.append(event.status["state"])
            if seen[-1] == "stopped":
                break
        assert seen[0] == "starting"
        assert "running" in seen
        assert seen[-1] == "stopped"
    finally:
        sub.close()


async def test_a_used_worker_is_never_reused(sup, src, settled):
    pids = []
    for _ in range(3):
        await sup.open_page("p1", [SectionSpec("s", src.oneshot)])
        await settled(sup, "p1")
        pids.append(sup.pids("p1")["s"])
    assert len(set(pids)) == 3, "a worker that ran user code was handed out again"
