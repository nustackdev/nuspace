"""nuverse's Planes: what creating ``jobs``, ``runs``, ``workers`` and ``planes`` seeds, and their cells."""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.utils import atomic
from nuspace.shapes import Reroot, Space, reroot
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Bracketed, Rewrites
from nuspace.system.services import ensure_system, init, supervisor
from nustd.ui import Session
from nuverse.planes import jobs, planes, runs, workers
from nuverse.snippets import program


LIVE = [jobs, runs, workers, planes]
CELLS = {
    "jobs": [("jobs", jobs.TABLE), ("new", jobs.NEW), ("job", jobs.DETAIL)],
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


class _Answering(_Recording):
    """A recording session that also answers reads, by the ref's own name."""

    def __init__(self, values: dict) -> None:
        super().__init__()
        self.values = values

    async def aread(self, path: tuple) -> object:
        return self.values[path[-1]]


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


# --- jobs ------------------------------------------------------------------------------------


def _cell(source: str) -> dict:
    """A cell's module namespace, its functions callable from here."""
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    return namespace


def _as(cell: str, term: nu.Nu, plane: str = "jp") -> nu.Nu:
    """``term`` as the Jobs plane's ``cell`` would run it: its state rerooted, its plane bound."""
    return nu.Let(ops.PLANE_ATTR, nu.Str(plane), reroot(term, plane, cell))


SELECTED = Space.planes["jp"].state["selected"]


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
    assert row["props"] == {"system": False, "ui": False, "made_by": "jobs"}
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
    await store.run(ops.add_plane("s", name="S", system=True) >> init.boot(job))
    await store.run(supervisor.supervise(job, "main", supervisor.ALWAYS, delay=5.0))
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
    await store.run(ops.add_cell(job, program.SOURCE, cell_id="more"))
    await store.run(init.boot(job))
    await _restart(store, job, supervisor.ALWAYS, 2.5)
    for cell in ("main", "more"):
        assert await store.read(supervisor.policy_of(job, cell)) == supervisor.ALWAYS
        assert await store.read(supervisor.delay_of(job, cell)) == 2.5
    session = _Recording()
    draw = _as("job", _cell(jobs.DETAIL)["draw"](nu.Str(job)))
    await nu.arun(draw, store.ctx.bind(Session, session))
    shown = {frame.ref[-1]: frame.payload for frame in session.frames}
    assert (shown["boot"], shown["choice"], shown["delay"]) == (True, "always", 2.5)
    assert shown["editor"] == program.SOURCE
    # No delay backs off, and off takes every cell off the supervisor.
    await _restart(store, job, supervisor.ON_FAILURE, 0.0)
    assert await store.read(supervisor.policy_of(job, "more")) == supervisor.ON_FAILURE
    assert await store.read(supervisor.delay_of(job, "more")) == -1.0
    await _restart(store, job, "off", 3.0)
    assert await store.read(supervisor.policy_of(job, "main")) == ""
    assert await store.read(supervisor.delay_of(job, "main")) == -1.0


async def test_deleting_a_job_cleans_boot_and_supervision(store):
    job = await _job(store)
    await store.run(init.boot(job) >> supervisor.supervise(job, "main", supervisor.ALWAYS, 1.0))
    await store.run(_as("job", _cell(jobs.DETAIL)["remove"](nu.Str(job))))
    assert job not in await store.read(ops.planes())
    assert job not in await store.read(init.booted())
    assert await store.read(supervisor.policy_of(job, "main")) == ""
    assert await store.read(supervisor.delay_of(job, "main")) == -1.0
    assert await store.read(SELECTED) == ""
