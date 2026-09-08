"""The ui channel: a worker's Session is IPC on the far side of a pipe.

``nu.ui.Session`` is three methods and every use site is
``rt.ctx.get(Session)``, so a section does not know or care that its
frames are crossing a process boundary. These tests drive real trees in
real workers against a loopback host.
"""

from __future__ import annotations

import asyncio

from nuspace.exec import SectionSpec


async def test_frames_route_out_of_the_worker(sup, host, src, settled):
    await sup.open_page("p1", [SectionSpec("s", src.oneshot)])
    await settled(sup, "p1")
    assert host.writes("sections.s.out") == ["hello"]
    page_id, section_id, _ = host.frames[0]
    assert (page_id, section_id) == ("p1", "s")


async def test_read_round_trips_through_the_host(sup, host, src, settled):
    host.values["probe"] = "abc"
    await sup.open_page("p1", [SectionSpec("r", src.reader)])
    await settled(sup, "p1")
    assert host.writes("sections.r.out") == ["abc"]


async def test_subscribe_and_notify_round_trip(sup, host, src, settled):
    host.values["probe"] = "first"
    await sup.open_page("p1", [SectionSpec("e", src.echo)])
    await settled(sup, "p1")
    await _until(lambda: sup.subscribers("probe") == ["e"])

    host.values["probe"] = "second"
    await sup.dispatch_notify("probe", "second")
    await _until(lambda: host.writes("sections.e.echo") == ["second"])


async def test_routes_are_dropped_when_the_section_goes_away(sup, host, src, settled):
    await sup.open_page("p1", [SectionSpec("e", src.echo)])
    await settled(sup, "p1")
    await _until(lambda: sup.subscribers("probe") == ["e"])
    await sup.close_page("p1")
    assert sup.subscribers("probe") == []
    # Nothing left to route to, and no exception on the way out.
    await sup.dispatch_notify("probe", "late")


async def test_two_sections_can_share_one_subscription_path(sup, host, src, settled):
    host.values["probe"] = "v"
    await sup.open_page(
        "p1",
        [SectionSpec("e1", src.echo), SectionSpec("e2", src.echo)],
    )
    await settled(sup, "p1")
    await _until(lambda: sorted(sup.subscribers("probe")) == ["e1", "e2"])

    await sup.dispatch_notify("probe", "v")
    await _until(
        lambda: host.writes("sections.e1.echo") and host.writes("sections.e2.echo"),
    )

    # Each worker owns its own session, so dropping one leaves the other
    # subscribed. No per-section handle registry needed.
    await sup.update_section("p1", SectionSpec("e1", src.live))
    await _until(lambda: sup.subscribers("probe") == ["e2"])


async def test_mount_fields_come_back_from_the_worker(sup, src, settled):
    await sup.open_page("p1", [SectionSpec("s", src.oneshot)])
    await settled(sup, "p1")
    assert sup.fields("p1", "s") == [{"path": "sections.s.out", "type": "TextRef"}]


async def _until(predicate, timeout: float = 5.0) -> None:
    """Poll a predicate. Async traffic crosses two processes here."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition never held")


async def test_nothing_runs_before_launch(sup, host, src):
    """Fields come back from compile; the tree waits for the go-ahead.

    This is the ordering the browser needs: mount fields ship first, so a
    section can never write into a slice that is not registered yet.
    """
    await sup.prepare_page("p1", [SectionSpec("t", src.ticker)])
    assert sup.fields("p1", "t") == [{"path": "sections.t.tick", "type": "TextRef"}]
    assert sup.status("p1")["t"]["state"] == "starting"

    await asyncio.sleep(0.3)
    assert host.frames == [], "a section ran before launch"

    await sup.launch_page("p1")
    await _until(lambda: bool(host.writes("sections.t.tick")))


async def test_prepare_section_returns_fields_before_running(sup, host, src, settled):
    await sup.open_page("p1", [SectionSpec("t", src.live)])
    await settled(sup, "p1")
    fields = await sup.prepare_section("p1", SectionSpec("t", src.ticker))
    assert fields == [{"path": "sections.t.tick", "type": "TextRef"}]
    await asyncio.sleep(0.2)
    assert not host.writes("sections.t.tick")
    await sup.launch_section("p1", "t")
    await _until(lambda: bool(host.writes("sections.t.tick")))
