"""nuverse's Planes: what creating ``jobs``, ``runs``, ``workers`` and ``planes`` seeds, and their cells."""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import Reroot, Space, States, reroot
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Bracketed, Rewrites
from nuspace.system.services import ensure_system, init, supervisor
from nustd.ui import Session
from nuverse.planes import jobs, planes, runs, workers
from nuverse.snippets import program


LIVE = [jobs, runs, workers, planes]
CELLS = {
    "jobs": [("jobs", jobs.TABLE), ("new", jobs.NEW), ("job", jobs.DETAIL)],
    "runs": [("counts", runs.COUNTS), ("live", runs.LIVE), ("cells", runs.CELLS)],
    "workers": [("counts", workers.COUNTS), ("workers", workers.TABLE)],
    "planes": [("made_by", planes.MADE_BY), ("planes", planes.TABLE)],
}


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


class _Answering(_Recording):
    """A recording session that also answers reads, by the ref's own name."""

    def __init__(self, values: dict) -> None:
        super().__init__()
        self.values = values

    async def aread(self, path: tuple) -> object:
        return self.values[path[-1]]


def _seed() -> nu.Nu:
    """One live plane run with two live cell runs on one worker, and an ended run and worker."""
    k = Space.kernel
    live, gone = k.runs["r1"], k.runs["r2"]
    w1, w2 = k.workers["w1"], k.workers["w2"]
    return atomic(
        ops.add_plane("p", name="P", backend="async")
        >> ops.add_cell("p", "x", cell_id="c", name="C")
        >> live.plane.set("p")
        >> live.backend.set("async")
        >> live.by.set("nav")
        >> live.started_at.set(nu.Float(100.0))
        >> live.cells["x1"].cell.set("c")
        >> live.cells["x1"].by.set("nav")
        >> live.cells["x1"].version.set(1)
        >> live.cells["x1"].worker.set("w1")
        >> live.cells["x1"].started_at.set(nu.Float(100.0))
        >> live.cells["x2"].cell.set("c")
        >> live.cells["x2"].by.set("reload")
        >> live.cells["x2"].version.set(2)
        >> live.cells["x2"].worker.set("w1")
        >> live.cells_running.add("x1")
        >> live.cells_running.add("x2")
        >> live.workers.add("w1")
        >> k.running.add("r1")
        >> w1.backend.set("async")
        >> w1.run.set("r1")
        >> w1.handle.set("7")
        >> w1.started_at.set(nu.Float(100.0))
        >> k.workers_running.add("w1")
        >> gone.plane.set("p")
        >> gone.exit.set("failed")
        >> w2.backend.set("mp")
        >> w2.run.set("r2")
        >> w2.exit.set("failed")
    )


@pytest.mark.parametrize("module", LIVE, ids=lambda m: m.PLANE.name)
async def test_each_plane_is_created_drawn_with_its_cells(store, module):
    spec = module.PLANE
    made = await store.run(ops.create_plane(spec, name="Live", plane_id="p1"))
    assert made == "p1"
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == "p1"]
    assert row["name"] == "Live"
    assert row["props"] == {"system": False, "ui": True, "made_by": spec.name, "backend": "async"}
    assert row["meta"] == {"editable": True, "full_width": False, "icon": f"lucide:{spec.icon}"}
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
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
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
        "runs": "1",
        "cells": "2",
        "workers": "1",
    }
    (live,) = (await _frames(store, runs.LIVE)).values()
    assert live["columns"] == ["Plane", "Backend", "By", "Cells", "Workers", "Age"]
    ((plane, backend, by, cells, workers_, age),) = live["rows"]
    assert (plane, backend, by, cells, workers_) == ("P", "async", "nav", 2, 1)
    assert age.endswith("s")
    (table,) = (await _frames(store, runs.CELLS)).values()
    assert table["columns"] == ["Plane", "Cell", "By", "Version", "Worker", "Age"]
    assert [r[:5] for r in table["rows"]] == [
        ["P", "C", "nav", 1, "w1"],
        ["P", "C", "reload", 2, "w1"],
    ]
    assert table["rows"][1][5] == "starting"


async def test_workers_draws_counts_and_a_table(store):
    await store.run(_seed())
    counts = await _frames(store, workers.COUNTS)
    assert {name: counts[name]["value"] for name in counts} == {
        "up": "1",
        "async": "1",
        "mp": "0",
    }
    (table,) = (await _frames(store, workers.TABLE)).values()
    assert table["columns"] == ["ID", "Backend", "Plane", "Run", "Cells", "Age"]
    assert [r[:5] for r in table["rows"]] == [["w1", "async", "P", "r1", 2]]


async def test_planes_draws_makers_and_every_plane(store):
    await store.run(
        ops.create_plane(runs.PLANE, name="R", plane_id="r")
        >> ops.add_plane("s", name="S", system=True, backend="async")
    )
    (made,) = (await _frames(store, planes.MADE_BY)).values()
    assert sorted(made["rows"]) == [["runs", 1, 3], ["system", 1, 0]]
    (table,) = (await _frames(store, planes.TABLE)).values()
    assert sorted(table["rows"]) == [["R", "runs", "no", 3], ["S", "", "yes", 0]]


# --- jobs ------------------------------------------------------------------------------------


def _cell(source: str) -> dict:
    """A cell's module namespace, its functions callable from here."""
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    return namespace


def _as(cell: str, term: nu.Nu, plane: str = "jp") -> nu.Nu:
    """``term`` as the Jobs plane's ``cell`` would run it: its state rerooted, its plane bound."""
    return nu.Let(ops.PLANE_ATTR, nu.Str(plane), reroot(term, plane, cell))


SELECTED = States.planes["jp"].state["selected"]


async def _job(store, name: str = "Nightly") -> str:
    """The service planes, the Jobs plane at ``jp``, and a job made by its ``new`` cell."""
    if not await store.read(ops.plane_exists("jp")):
        await store.run(ensure_system() >> ops.create_plane(jobs.PLANE, plane_id="jp"))
    await store.run(_as("new", _cell(jobs.NEW)["create"](nu.Str(name))))
    return await store.read(SELECTED)


async def test_the_jobs_plane_registers_after_plain():
    from nuverse.planes import PLANES

    assert [p.name for p in PLANES[:2]] == ["plain", "jobs"]
    assert (jobs.PLANE.label, jobs.PLANE.icon) == ("Jobs", "briefcase")


async def test_creating_a_job_makes_a_headless_plane_with_a_main_cell(store):
    job = await _job(store)
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == job]
    assert row["name"] == "Nightly"
    assert row["props"] == {"system": False, "ui": False, "made_by": "jobs", "backend": "mp"}
    assert row["parent"] == "jp"
    assert await store.read(ops.cell_rows(job)) == [
        {
            "id": "main",
            "name": "main",
            "prog": program.SOURCE,
            "props": {"made_by": "", "has_ui": False},
            "meta": {},
        }
    ]


async def test_the_jobs_table_lists_jobs_only_and_selects_on_click(store):
    job = await _job(store)
    other = await _job(store, "Hourly")
    await store.run(ops.add_plane("s", name="S", system=True, backend="async") >> init.boot(job))
    await store.run(supervisor.supervise(job, supervisor.ALWAYS, delay=5.0))
    (table,) = (await _frames(store, jobs.TABLE)).values()
    assert table["rows"] == [
        ["Nightly", job, "yes", "always, 5s", "no"],
        ["Hourly", other, "no", "off", "no"],
    ]
    select = _cell(jobs.TABLE)["select"]()
    await store.run(_as("jobs", nu.Let("click", nu.Literal({"row_index": 0}), select)))
    assert await store.read(SELECTED) == job


async def _restart(store, job: str, policy: str, delay: float) -> None:
    """The ``job`` cell's restart handler, the select and delay reading as given."""
    session = _Answering({"choice": policy, "delay": delay})
    term = _as("job", _cell(jobs.DETAIL)["restart"](nu.Str(job), "t"))
    await nu.arun(term, store.ctx.bind(Session, session))


async def test_boot_and_restart_settings_round_trip(store):
    job = await _job(store)
    await store.run(init.boot(job))
    await _restart(store, job, supervisor.ALWAYS, 2.5)
    assert await store.read(supervisor.policy_of(job)) == supervisor.ALWAYS
    assert await store.read(supervisor.delay_of(job)) == 2.5
    session = _Recording()
    draw = _as("job", _cell(jobs.DETAIL)["draw"](nu.Str(job)))
    await nu.arun(draw, store.ctx.bind(Session, session))
    shown = {frame.ref[-1]: frame.payload for frame in session.frames}
    assert (shown["boot"], shown["choice"], shown["delay"]) == (True, "always", 2.5)
    assert shown["editor"] == program.SOURCE
    # No delay backs off, and off takes the job off the supervisor.
    await _restart(store, job, supervisor.ON_FAILURE, 0.0)
    assert await store.read(supervisor.policy_of(job)) == supervisor.ON_FAILURE
    assert await store.read(supervisor.delay_of(job)) == -1.0
    await _restart(store, job, "off", 3.0)
    assert await store.read(supervisor.policy_of(job)) == ""
    assert await store.read(supervisor.delay_of(job)) == -1.0


async def test_deleting_a_job_cleans_boot_and_supervision(store):
    job = await _job(store)
    await store.run(init.boot(job) >> supervisor.supervise(job, supervisor.ALWAYS, 1.0))
    await store.run(_as("job", _cell(jobs.DETAIL)["remove"](nu.Str(job))))
    assert job not in await store.read(ops.planes())
    assert job not in await store.read(init.booted())
    assert await store.read(supervisor.policy_of(job)) == ""
    assert await store.read(supervisor.delay_of(job)) == -1.0
    assert await store.read(SELECTED) == ""


def test_every_plane_names_a_registered_backend():
    from nuspace.system.backends import BACKENDS
    from nuverse.planes import PLANES

    assert all(spec.backend in BACKENDS for spec in PLANES)
    assert {spec.name: spec.backend for spec in PLANES} == dict.fromkeys(
        ("plain", "jobs", "runs", "workers", "planes"), "async"
    )
