"""Sections that touch kv, not just ui.

A section's tree is bracketed in a kv navigator inside the worker, so
``Space.state`` works the same as it does in-process. What is *not* the
same is sharing: RocksDB takes an exclusive directory lock, so N workers
cannot all be writers against one store. ``memory`` is per-worker
scratch and is what these tests use.
"""

from __future__ import annotations

from nuspace.exec import LoopbackHost, SectionSpec, Supervisor


async def test_section_writes_and_reads_kv(bounds, src):
    host = LoopbackHost()
    sup = Supervisor(host, pool_size=1, store={"kind": "memory"}, timeouts=bounds.timeouts)
    await sup.astart()
    try:
        await sup.open_page("p1", [SectionSpec("s", src.kv_round_trip)])
        await sup.wait_for("p1", {"stopped"}, timeout=20.0)
        assert host.writes("sections.s.out") == ["v"]
    finally:
        await sup.aclose()


async def test_workers_do_not_share_a_memory_store(bounds, src):
    """Each worker brackets its own navigator. Scratch is per section."""
    host = LoopbackHost()
    sup = Supervisor(host, pool_size=2, store={"kind": "memory"}, timeouts=bounds.timeouts)
    await sup.astart()
    try:
        await sup.open_page(
            "p1",
            [SectionSpec("w", src.kv_round_trip), SectionSpec("r", src.kv_reader)],
        )
        await sup.wait_for("p1", {"stopped", "failed"}, timeout=20.0)
        assert host.writes("sections.w.out") == ["v"]
        assert host.writes("sections.r.out") != ["v"]
    finally:
        await sup.aclose()
