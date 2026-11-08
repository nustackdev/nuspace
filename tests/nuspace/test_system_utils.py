"""The error policies every fold arm runs under, and the web arms built on them."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.ops import init_stores
from nuspace.ops.utils import atomic_state
from nuspace.shapes import CellState, Space, States, reroot
from nuspace.system.devices.web.utils import Arms
from nuspace.system.utils import isolated, report, restarting, snap


#: A command that raises when it runs: a flow body must be one.
BOOM = nu.print(nu.Div(1, 0))


def _lines(capsys) -> list[str]:
    return capsys.readouterr().out.splitlines()


async def _run(term: nu.Nu) -> object:
    value, _ = await nu.arun(term)
    return value


# --- report and the policies ---------------------------------------------------


async def test_report_says_name_id_and_error_on_one_line(capsys):
    await _run(report("reload", "p1", nu.Str("boom")) >> report("init", None, nu.Str("gone")))
    assert _lines(capsys) == ["nuspace reload p1: boom", "nuspace init: gone"]


async def test_isolated_reports_the_raise_and_ends_the_arm(capsys):
    await _run(isolated(BOOM, "web viewer", "planes.open") >> nu.print("after"))
    assert _lines(capsys) == ["nuspace web viewer planes.open: division by zero", "after"]


async def test_isolated_passes_a_clean_arm_through(capsys):
    await _run(isolated(nu.print("ran"), "x"))
    assert _lines(capsys) == ["ran"]


async def test_restarting_runs_a_failing_arm_again_and_reports_every_failure(capsys):
    """Fails, waits the delay, fails again: a report per failure, the same wait each time."""
    await _run(nu.Race(restarting(BOOM, "supervisor", "p1", delay=0.1), nu.Delay(1.5)))
    lines = _lines(capsys)
    # No backoff: about fifteen attempts fit, where a doubling wait (0.1, 0.2, 0.4, 0.8) fits four.
    assert len(lines) >= 6, lines
    assert set(lines) == {"nuspace supervisor p1: division by zero"}


async def test_restarting_waits_its_delay_between_attempts(capsys):
    """A long delay: one failure, then the wait, nothing else before the race ends it."""
    await _run(nu.Race(restarting(BOOM, "reload", delay=5.0), nu.Delay(0.5)))
    assert _lines(capsys) == ["nuspace reload: division by zero"]


async def test_restarting_ends_with_a_clean_arm(capsys):
    await _run(restarting(nu.print("ran"), "nav"))
    assert _lines(capsys) == ["ran"]


# --- web arms ----------------------------------------------------------------------


class _Tick(CellState):
    a = nustd.kv.IntRef.slot()
    b = nustd.kv.IntRef.slot()


def _at(term: nu.Nu) -> nu.Nu:
    return reroot(term, "p", "c")


def _stores(body: nu.Nu) -> nu.Nu:
    return nu.With(
        nustd.kv.memory_navigator(tags=(Space,)),
        nustd.kv.memory_navigator(tags=(States,)),
        body=init_stores() >> body,
    )


def _bump(ref: nu.Nu) -> nu.Nu:
    return atomic_state(_at(ref.set(ref.fallback(0) + 1)))


def _ship() -> nu.Nu:
    return nu.print(snap(_at(_Tick.a.fallback(0))), snap(_at(_Tick.b.fallback(0))))


def _states(ship: nu.Nu) -> nu.Nu:
    return Arms("t").states(
        "tick", [snap(_at(_Tick.a.on_change())), snap(_at(_Tick.b.on_change()))], ship
    )


async def test_states_ships_on_a_change_of_any_filter(capsys):
    steps = nu.Delay(0.2) >> _bump(_Tick.a) >> nu.Delay(0.2) >> _bump(_Tick.b) >> nu.Delay(0.2)
    await _run(_stores(nu.Race(_states(_ship()), steps)))
    lines = _lines(capsys)
    assert lines[0] == "0 0"
    assert "1 0" in lines
    assert lines[-1] == "1 1"


async def test_states_guard_reports_a_raising_ship_and_keeps_the_feed(capsys):
    """A ship that raises is reported per wake; the arm stays subscribed."""
    steps = nu.Delay(0.2) >> _bump(_Tick.a) >> nu.Delay(0.2)
    await _run(_stores(nu.Race(_states(BOOM), steps)))
    lines = _lines(capsys)
    assert len(lines) >= 2
    assert set(lines) == {"nuspace web t tick: division by zero"}


async def test_guard_ends_a_dead_arm_without_taking_its_siblings(capsys):
    arms = Arms("t")
    dead = arms.guard(BOOM, "dead")
    alive = nu.Delay(0.1) >> nu.print("alive")
    await _run(nu.ParallelAsync(dead, alive))
    assert _lines(capsys) == ["nuspace web t dead: division by zero", "alive"]
