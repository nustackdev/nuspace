"""The core ops tell telemetry what they made, by hand, from a spec or by nuspace, and what they removed."""

from __future__ import annotations

import pytest

import nu
import nuspace
from nuspace import _telemetry
from nuspace.errors import Exists


@pytest.fixture
def told(monkeypatch):
    events: list[str] = []
    monkeypatch.setattr(_telemetry, "track", events.append)
    return events


async def do(store, term):
    return await store.run(nuspace.atomic(term))


async def test_made_by_hand_is_told_plain(store, told):
    await do(
        store,
        nuspace.plane.add("a")
        >> nuspace.plane.add("b", parent="a")
        >> nuspace.cell.add("a", "src", id="c1")
        >> nuspace.cell.add("b", "src", id="c2", fabrics=[]),
    )
    assert sorted(told) == ["cell_created"] * 2 + ["plane_created"] * 2


async def test_made_from_a_spec_is_told_as_spec(store, told):
    await do(
        store,
        nuspace.plane.add("a", spec="pkg.notes")
        >> nuspace.cell.add("a", "src", id="c1", origin="spec")
        >> nuspace.cell.add("a", "src", id="c2", spec="pkg.chart"),
    )
    assert sorted(told) == ["cell_created_spec"] * 2 + ["plane_created_spec"]


async def test_made_by_nuspace_is_told_as_system_over_spec(store, told):
    await do(
        store,
        nuspace.plane.add("s", system=True, spec="pkg.notes")
        >> nuspace.cell.add("s", "src", id="c", spec="pkg.chart", origin="system"),
    )
    assert sorted(told) == ["cell_created_system", "plane_created_system"]


async def test_args_known_only_when_run_pick_the_event_then(store, told):
    await do(
        store,
        nuspace.plane.add("s", system=nu.Bool(True))
        >> nuspace.plane.add("a", spec=nu.Str("pkg.notes"))
        >> nuspace.plane.add("b", system=nu.Bool(False), spec=nu.Str("")),
    )
    assert sorted(told) == ["plane_created", "plane_created_spec", "plane_created_system"]


async def test_removing_tells_each_row_of_the_subtree(store, told):
    await do(
        store,
        nuspace.plane.add("a")
        >> nuspace.plane.add("b", parent="a")
        >> nuspace.cell.add("a", "src", id="c1")
        >> nuspace.cell.add("b", "src", id="c2")
        >> nuspace.cell.add("b", "src", id="c3"),
    )
    told.clear()
    await do(store, nuspace.cell.remove("c3"))
    assert told == ["cell_removed"]
    told.clear()
    await do(store, nuspace.plane.remove("a"))
    assert sorted(told) == ["cell_removed"] * 2 + ["plane_removed"] * 2


async def test_a_refused_op_tells_nothing(store, told):
    await do(store, nuspace.plane.add("a"))
    told.clear()
    with pytest.raises(Exists):
        await do(store, nuspace.plane.add("a"))
    assert told == []


def test_every_told_event_may_be_sent():
    for what in ("plane", "cell"):
        for suffix in ("", "_spec", "_system"):
            assert f"{what}_created{suffix}" in _telemetry.EVENTS
        assert f"{what}_removed" in _telemetry.EVENTS


async def test_restoring_tells_each_row_it_brings_back(store, told):
    await do(
        store,
        nuspace.plane.add("a")
        >> nuspace.plane.add("b", parent="a")
        >> nuspace.cell.add("a", "src", id="c1")
        >> nuspace.cell.add("b", "src", id="c2"),
    )
    await do(store, nuspace.cell.remove("c1") >> nuspace.plane.remove("a"))
    told.clear()
    await do(store, nuspace.plane.restore("a"))
    assert sorted(told) == ["cell_restored"] + ["plane_restored"] * 2
    told.clear()
    await do(store, nuspace.cell.restore("c1"))
    assert told == ["cell_restored"]
