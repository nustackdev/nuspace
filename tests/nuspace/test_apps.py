"""Apps v1: the invariants that make "always" mean something.

Apps and sections are the same substance and share a supervisor, so the
section-level facts (compile, status contract, per-unit isolation) are
already pinned in ``test_pages.py`` and are not re-tested here.

What *is* tested is the part that differs, and it is all lifetime:

- The supervisor is created by the space, not by a connection, so apps
  run with nothing attached.
- Two connections observe one runtime, not one each.
- A connection joining mid-run sees running apps and starts nothing.
- Editing an app restarts that app and only that app.
- Reconcile does not resurrect an app that stopped or died.
"""

from __future__ import annotations

import asyncio
import textwrap
from types import SimpleNamespace

import pytest

import nu
from nu.engine.structure import Declared
from nu.kv.tree import auto_flow_atomic
from nu.lang import Control
from nuspace.core.shapes import Space
from nuspace.web.refs.apps import (
    AppSpec,
    AppsRuntime,
    AppsSupervisor,
    View,
    get_runtime,
    new_app_source,
)
from nuspace.web.refs.apps.interactions import AppOps
from nuspace.web.refs.apps.runtime import install_runtime
from nuspace.web.refs.apps.store import app_row, ordered_apps


# -- helpers -----------------------------------------------------------------


def program(body: str, *, head: str = "", takes_path: bool = True) -> str:
    """An app source: a module with an ``out`` entry point returning a term."""
    params = "path" if takes_path else ""
    expr = textwrap.indent(textwrap.dedent(body).strip(), " " * 8)
    preamble = "import nu\n"
    if head:
        preamble += textwrap.dedent(head).strip() + "\n"
    return f"{preamble}\n\ndef out({params}):\n    return (\n{expr}\n    )\n"


# Writes a counter into kv forever. This is the "did it run with no browser"
# probe: the number is the number of ticks that happened unobserved.
COUNTER = program(
    """
    nu.ForeverDo(
        Space.state.set_item(
            'beats',
            nu.ToStr(nu.Add(nu.ToInt(nu.If(Space.state.contains('beats'),
                                           nu.ToStr(Space.state['beats']),
                                           nu.Str('0'))),
                            nu.Int(1))),
        )
        >> nu.Delay(0.01)
    )
    """,
    head="from nuspace.core.shapes import Space",
    takes_path=False,
)

# Names its own kv namespace off `path`, which is the one scope value an app
# gets. Headless: no ui ref anywhere.
NAMESPACED = program(
    "Space.state.set_item(path + '.hello', nu.Str('yes'))",
    head="from nuspace.core.shapes import Space",
)

LIVE = program("nu.ForeverDo(nu.Delay(0.02))", takes_path=False)
ONESHOT = program(
    "Space.state.set_item('once', nu.Str('done'))",
    head="from nuspace.core.shapes import Space",
    takes_path=False,
)
RAISES = program("nu.Div(nu.Int(1), nu.Int(0))", takes_path=False)
BROKEN = "def out(path):\n    return nu.Str('unclosed'\n"


async def _run(term: nu.Nu, ctx: object) -> object:
    value, _ = await nu.arun(auto_flow_atomic(term, scope=Space), ctx)  # type: ignore[arg-type]
    return value


async def _await_states(runtime: AppsRuntime, wanted: set[str], *, timeout: float = 5.0) -> None:
    """Poll until every known app has settled into one of ``wanted``."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        rows = runtime.statuses()
        if rows and all(r["state"] in wanted for r in rows):
            return
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"never settled into {wanted}: {rows}")
        await asyncio.sleep(0.01)


@pytest.fixture
async def space():
    """A memory-backed space, its ctx, and a seeded-apps helper.

    No browser, no server, no ui Session anywhere -- which is exactly the
    environment an app is supposed to run in.
    """
    navigator = nu.kv.memory_navigator(tags=(Space,))
    ctx_box: dict[str, object] = {}
    ready = asyncio.Event()
    done = asyncio.Event()

    class _Capture(Control):
        """Hand the ctx inside the ``nu.With`` bracket out to the test.

        A space's tree is the only place a navigator-bound ctx exists, and
        that ctx is precisely what ``AppsRunner`` hands the runtime. So the
        fixture stands in for the runner rather than faking a ctx.
        """

        _mutates = Declared(value=frozenset(), name="mutates")
        _requires_async = Declared(value=True, name="requires_async")

        def _compile(self, nid, children):
            def thunk(rt) -> None:
                raise RuntimeError("async only")

            return thunk

        def _acompile(self, nid, children):
            async def athunk(rt) -> None:
                ctx_box["ctx"] = rt.ctx
                ready.set()
                await done.wait()

            return athunk

    task = asyncio.create_task(nu.arun(nu.With(navigator, body=_Capture())))
    await asyncio.wait_for(ready.wait(), timeout=5.0)
    ctx = ctx_box["ctx"]

    async def seed(apps: dict[str, str]) -> None:
        for aid, source in apps.items():
            await _run(
                Space.apps.set_item(
                    aid,
                    {"name": aid, "snippet": source, "policy": "always"},
                ),
                ctx,
            )

    async def read_state(key: str) -> object:
        return await _run(
            nu.If(Space.state.contains(key), nu.ToStr(Space.state[key]), nu.Str("")),
            ctx,
        )

    yield SimpleNamespace(ctx=ctx, seed=seed, read_state=read_state)

    done.set()
    await asyncio.wait_for(task, timeout=5.0)


# -- the load-bearing one ----------------------------------------------------


async def test_apps_run_with_nothing_attached(space):
    """No connection, no driver, no Session. The runner alone makes apps run."""
    await space.seed({"a_counter": COUNTER})

    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        loop = asyncio.create_task(runtime.arun())
        try:
            await _await_states(runtime, {"running"})
            await asyncio.sleep(0.2)
            beats = await space.read_state("beats")
        finally:
            loop.cancel()
            await asyncio.gather(loop, return_exceptions=True)

    # It ticked while nobody was looking. That is the whole pillar.
    assert int(beats) > 1


async def test_app_entry_point_gets_its_own_kv_namespace(space):
    """``path`` is ``apps.<id>``: a kv namespace, not a ui mount prefix."""
    await space.seed({"a_ns": NAMESPACED})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        await runtime.reconcile()
        await _await_states(runtime, {"running", "stopped"})
        assert await space.read_state("apps.a_ns.hello") == "yes"
        await runtime._supervisor.stop_all()


# -- observation, not ownership ----------------------------------------------


async def test_a_late_observer_sees_running_apps(space):
    """A browser connecting mid-run reads status; it does not start anything."""
    await space.seed({"a_live": LIVE})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        loop = asyncio.create_task(runtime.arun())
        try:
            await _await_states(runtime, {"running"})
            started_at = runtime.status("a_live")["started_at"]

            # ... time passes, then a connection arrives and looks it up.
            await asyncio.sleep(0.1)
            found = get_runtime(Space)
            assert found is runtime
            joined = found.status("a_live")

            assert joined["state"] == "running"
            # Same generation, not a fresh one started on our behalf.
            assert joined["started_at"] == started_at
        finally:
            loop.cancel()
            await asyncio.gather(loop, return_exceptions=True)


async def test_two_observers_share_one_runtime(space):
    """Two connections, one set of apps -- and two independent status feeds."""
    await space.seed({"a_live": LIVE})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        first: list[dict] = []
        second: list[dict] = []
        runtime.on_change(first.append)
        runtime.on_change(second.append)

        assert get_runtime(Space) is get_runtime(Space)

        await runtime.reconcile()
        await _await_states(runtime, {"running"})

        assert len(runtime.statuses()) == 1
        assert [e["state"] for e in first] == [e["state"] for e in second]

        # One connection drops. The other keeps hearing, apps keep running.
        runtime.off_change(first.append)
        runtime.off_change(second.append)
        await runtime._supervisor.stop_all()


async def test_runtime_is_withdrawn_when_the_runner_ends(space):
    """A driver can never hold a handle on a supervisor whose loop has stopped."""
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        assert get_runtime(Space) is runtime
    assert get_runtime(Space) is None


# -- reconcile ---------------------------------------------------------------


async def test_editing_one_app_restarts_only_that_one(space):
    await space.seed({"a_one": LIVE, "a_two": LIVE})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        await runtime.reconcile()
        await _await_states(runtime, {"running"})
        before = {r["section_id"]: r["started_at"] for r in runtime.statuses()}

        await asyncio.sleep(0.02)
        await _run(Space.apps["a_two"].snippet.set(nu.Str(ONESHOT)), space.ctx)
        await runtime.reconcile()
        await _await_states(runtime, {"running", "stopped"})

        after = {r["section_id"]: r["started_at"] for r in runtime.statuses()}
        assert after["a_one"] == before["a_one"]
        assert after["a_two"] != before["a_two"]
        await runtime._supervisor.stop_all()


async def test_reconcile_does_not_resurrect_a_settled_app(space):
    """The one rule that differs from pages: only a source change restarts."""
    await space.seed({"a_dead": RAISES, "a_done": ONESHOT})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        await runtime.reconcile()
        await _await_states(runtime, {"failed", "stopped"})
        settled = {r["section_id"]: (r["state"], r["started_at"]) for r in runtime.statuses()}

        for _ in range(3):
            await runtime.reconcile()
            await asyncio.sleep(0.01)

        again = {r["section_id"]: (r["state"], r["started_at"]) for r in runtime.statuses()}
        assert again == settled
        assert settled["a_dead"][0] == "failed"
        assert settled["a_done"][0] == "stopped"


async def test_removing_an_app_from_kv_stops_it(space):
    await space.seed({"a_live": LIVE})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        await runtime.reconcile()
        await _await_states(runtime, {"running"})

        await _run(Space.apps.del_item("a_live"), space.ctx)
        await runtime.reconcile()

        assert runtime.statuses() == []


async def test_a_source_that_will_not_compile_is_invalid(space):
    """`invalid` never produced a tree, so it never ran. Distinct from failed."""
    await space.seed({"a_broken": BROKEN})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        await runtime.reconcile()
        status = runtime.status("a_broken")
        assert status["state"] == "invalid"
        assert status["error"]
        assert status["started_at"] is None


async def test_an_explicit_restart_revives_a_failed_app(space):
    """Reconcile will not, but asking will. That is the point of asking."""
    await space.seed({"a_dead": RAISES})
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        await runtime.reconcile()
        await _await_states(runtime, {"failed"})
        first = runtime.status("a_dead")["started_at"]

        await asyncio.sleep(0.02)
        await runtime.restart("a_dead")
        await _await_states(runtime, {"failed"})

        assert runtime.status("a_dead")["started_at"] != first


# -- the spec ----------------------------------------------------------------


def test_app_prefix_is_a_kv_namespace():
    assert AppSpec("a_x", "").prefix == "apps.a_x"


def test_apps_supervisor_is_a_section_supervisor():
    """Same substance, same supervisor. Only the restart rule is overridden."""
    from nuspace.web.refs.pages.supervise import LocalSupervisor

    assert issubclass(AppsSupervisor, LocalSupervisor)


def test_ordered_apps_is_creation_order():
    """Ids are time-ordered, so key order is the only order a flat list needs."""
    raw = {"a_c": {}, "a_a": {}, "a_b": {}, "junk": "not a dict"}
    assert [aid for aid, _ in ordered_apps(raw)] == ["a_a", "a_b", "a_c"]


def test_an_app_row_reads_source_off_the_snippet_slot():
    row = app_row("a_x", {"name": "n", "snippet": "src"}, None)
    assert row == {"id": "a_x", "name": "n", "source": "src", "policy": "always", "status": None}


def test_new_app_source_addresses_this_space_root():
    """A constant naming ``Space`` would fail the moment a subclassed space ran it."""
    assert f"from {Space.__module__} import Space" in new_app_source(Space)


# -- the surface -------------------------------------------------------------


async def test_a_detached_space_ships_attached_false(space):
    """No runner mounted is a renderable answer, not an error and not loading."""
    view = View(space.ctx, Space)
    payload = await view.apps_payload()
    assert payload == {"op": "set_apps", "apps": [], "attached": False}


async def test_the_app_ops_write_kv_and_the_payload_follows(space):
    """Four ops, one substrate. Nothing here ships -- kv notifies and ship paints."""
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        view = View(space.ctx, Space)
        ops = AppOps(view)
        await ops.init_apps()

        await ops.create(name="fresh")
        payload = await view.apps_payload()
        assert payload["attached"] is True
        assert [a["name"] for a in payload["apps"]] == ["fresh"]
        aid = payload["apps"][0]["id"]

        await ops.rename(app_id=aid, name="renamed")
        await ops.update(app_id=aid, source=LIVE)
        row = (await view.apps_payload())["apps"][0]
        assert (row["name"], row["source"]) == ("renamed", LIVE)

        await ops.delete(app_id=aid)
        assert (await view.apps_payload())["apps"] == []
        await view.dispose()


async def test_a_view_drops_its_status_listener_on_dispose(space):
    """The runtime outlives the connection, so a leaked listener leaks forever."""
    runtime = AppsRuntime(space.ctx, Space)
    with install_runtime(Space, runtime):
        view = View(space.ctx, Space)
        assert view.observe() is runtime
        assert len(runtime._listeners) == 1

        await view.dispose()
        assert runtime._listeners == []
