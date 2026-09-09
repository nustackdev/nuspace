"""Warm-open latency: does worker-per-section survive contact with a page?

Page open has to feel instant. If handing eight warm workers a section
each costs more than a frame or two, worker-per-section collapses into
worker-per-page and the isolation story goes with it.

The bound asserted here is deliberately loose (it is a shared CI box, not
a benchmark rig); the number that matters is printed.
"""

from __future__ import annotations

import time

import pytest

from nuspace.exec import LoopbackHost, SectionSpec, Supervisor


SECTIONS = 8


@pytest.mark.parametrize("warm", [True, False], ids=["warm", "cold"])
async def test_page_open_latency(warm, bounds, settled, capsys, src):
    host = LoopbackHost()
    sup = Supervisor(host, pool_size=SECTIONS if warm else 0, timeouts=bounds.timeouts)
    started = time.perf_counter()
    await sup.astart()
    prewarm = time.perf_counter() - started
    try:
        specs = [
            SectionSpec(f"s{i}", src.realistic[i % len(src.realistic)]) for i in range(SECTIONS)
        ]
        t0 = time.perf_counter()
        await sup.open_page("page", specs)
        dispatched = time.perf_counter() - t0
        await settled(sup, "page")
        running = time.perf_counter() - t0

        with capsys.disabled():
            print(
                f"\n[{'warm' if warm else 'cold'}] {SECTIONS} sections: "
                f"prewarm {prewarm * 1000:.0f}ms, "
                f"dispatch {dispatched * 1000:.1f}ms, "
                f"all-running {running * 1000:.1f}ms",
            )

        assert len(set(sup.pids("page").values())) == SECTIONS
        if warm:
            # Warm open is a message round trip per section, not an
            # interpreter start. Anything near a second means the pool
            # is not doing its job.
            assert running < 1.0
    finally:
        await sup.aclose()
