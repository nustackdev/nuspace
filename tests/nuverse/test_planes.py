"""nuverse's Planes: what creating ``runs``, ``workers`` and ``planes`` seeds, and their cells."""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Bracketed, Rewrites
from nustd.ui import Session
from nuverse.planes import planes, runs, workers


LIVE = [runs, workers, planes]
CELLS = {
    "runs": [("counts", runs.COUNTS), ("live", runs.LIVE), ("finished", runs.FINISHED)],
    "workers": [("counts", workers.COUNTS), ("workers", workers.TABLE)],
    "planes": [("made_by", planes.MADE_BY), ("planes", planes.TABLE)],
}


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


def _seed() -> nu.Nu:
    """A worker up with one live run, one dead worker, and two finished runs."""
    k = Space.kernel
    w1, w2 = k.workers["w1"], k.workers["w2"]
    live, ok, bad = k.runs["r1"], k.runs["r2"], k.runs["r3"]
    return atomic(
        w1.kind.set("local")
        >> w1.status.set("up")
        >> w1.held.set(True)
        >> w1.started.set(nu.Float(100.0))
        >> k.active.set_item("w1", nu.Bool(True))
        >> w2.kind.set("local")
        >> w2.status.set("dead")
        >> live.plane.set("p")
        >> live.cell.set("c")
        >> live.worker.set("w1")
        >> live.by.set("nav")
        >> live.status.set("up")
        >> live.started.set(nu.Float(100.0))
        >> k.live.set_item("r1", "w1")
        >> ok.plane.set("gone")
        >> ok.status.set("dead")
        >> ok.exit.set("ok")
        >> ok.ended.set(nu.Float(50.0))
        >> bad.plane.set("p")
        >> bad.status.set("dead")
        >> bad.exit.set("failed")
        >> bad.error.set("x" * 200)
        >> bad.ended.set(nu.Float(60.0))
    )


@pytest.mark.parametrize("module", LIVE, ids=lambda m: m.PLANE.name)
async def test_each_plane_is_created_drawn_with_its_cells(store, module):
    spec = module.PLANE
    made = await store.run(ops.create_plane(spec, name="Live", plane_id="p1"))
    assert made == "p1"
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == "p1"]
    assert row["name"] == "Live"
    assert row["props"] == {"system": False, "ui": True, "made_by": spec.name}
    assert row["meta"] == {"editable": True, "full_width": False}
    cells = await store.read(ops.cell_rows("p1"))
    assert [(c["name"], c["prog"]) for c in cells] == CELLS[spec.name]


async def test_a_minted_plane_yields_its_id_and_takes_the_label(store):
    made = await store.run(ops.create_plane(runs.PLANE))
    assert made in await store.read(ops.planes())
    assert await store.read(Space.planes[made].name) == "Runs"
    assert len(await store.read(ops.cells(made))) == 3


@pytest.mark.parametrize(
    "source", [s for cells in CELLS.values() for _, s in cells], ids=lambda s: str(hash(s))
)
async def test_each_cell_loads_through_the_kernel_rewrites(store, source):
    await store.run(ops.add_plane("p") >> ops.add_cell("p", source, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite, Bracketed())
    prog = Space.planes["p"].cells["c"].prog
    term = await store.run(
        nustd.kv.auto_flow_atomic(
            prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


def _draw(source: str) -> nu.Nu:
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    return namespace["draw"]()


async def _frames(store, source: str) -> dict:
    """One draw of a cell against the seeded store: ``{ref name: payload}``."""
    session = _Recording()
    await nu.arun(_draw(source), store.ctx.bind(Session, session))
    return {frame.ref[-1]: frame.payload for frame in session.frames}


async def test_runs_draws_counts_and_tables(store):
    await store.run(_seed())
    counts = await _frames(store, runs.COUNTS)
    assert {name: counts[name]["value"] for name in counts} == {
        "live": "1",
        "ok": "1",
        "failed": "1",
        "killed": "0",
    }
    (live,) = (await _frames(store, runs.LIVE)).values()
    assert live["columns"] == ["Plane", "Cell", "Worker", "By", "Status", "Age"]
    ((plane, cell, worker, by, status, age),) = live["rows"]
    assert (plane, cell, worker, by, status) == ("p", "c", "w1", "nav", "up")
    assert age.endswith("s")
    (done,) = (await _frames(store, runs.FINISHED)).values()
    assert [(r[0], r[2], len(r[3])) for r in done["rows"]] == [
        ("p", "failed", 80),
        ("gone", "ok", 0),
    ]


async def test_workers_draws_counts_and_a_table(store):
    await store.run(_seed())
    counts = await _frames(store, workers.COUNTS)
    assert {name: counts[name]["value"] for name in counts} == {
        "starting": "0",
        "up": "1",
        "stopping": "0",
        "dead": "1",
    }
    (table,) = (await _frames(store, workers.TABLE)).values()
    assert [r[:5] for r in table["rows"]] == [
        ["w2", "local", "dead", "no", 0],
        ["w1", "local", "up", "yes", 1],
    ]


async def test_planes_draws_makers_and_every_plane(store):
    await store.run(
        ops.create_plane(runs.PLANE, name="R", plane_id="r")
        >> ops.add_plane("s", name="S", system=True)
    )
    (made,) = (await _frames(store, planes.MADE_BY)).values()
    assert sorted(made["rows"]) == [["runs", 1, 3], ["system", 1, 0]]
    (table,) = (await _frames(store, planes.TABLE)).values()
    assert sorted(table["rows"]) == [["R", "runs", "no", 3], ["S", "", "yes", 0]]
