"""The assembled tree: shape, law gate, and what has to survive a pickle."""

from __future__ import annotations

import pickle

import pytest

import nu
import nu.mp
import nu.prog
from nu.lang import compile as nu_compile
from nu.lang import validate
from nuspace.runner import Slot, app_body, app_path, fan_out, run_nu, runner_tree, slot_body
from nuspace.runner.dispatch import AtomicUnder


def test_app_path_is_a_kv_namespace():
    assert app_path("a_01") == "apps.a_01"


def test_app_body_is_an_eval_over_a_rewritten_load():
    body = app_body("a_01")
    assert isinstance(body, nu.prog.Eval)
    assert isinstance(body._children[0], AtomicUnder)


def test_slot_body_teleports_to_its_own_tag():
    body = slot_body(Slot(("w", 3), ("a_01",)))
    assert isinstance(body, nu.mp.Teleport)
    assert body._payload["target"] == ("w", 3)


def test_a_batched_slot_is_one_teleport():
    body = slot_body(Slot(("w", 0), ("a_01", "a_02")))
    assert isinstance(body, nu.mp.Teleport)
    assert isinstance(body._children[0], nu.ParallelAsync)


def test_an_idle_slot_dispatches_nothing():
    assert isinstance(slot_body(Slot(("w", 0), ())), nu.Noop)
    assert isinstance(fan_out((Slot(("w", 0), ()),)), nu.Noop)


def test_fan_out_skips_idle_slots():
    slots = (Slot(("w", 0), ("a",)), Slot(("w", 1), ()), Slot(("w", 2), ("b",)))
    body = fan_out(slots)
    assert isinstance(body, nu.ParallelAsync)
    assert len(body._children) == 2


def test_run_nu_is_just_a_teleport():
    tree = run_nu(nu.Noop(), target=("w", 7))
    assert isinstance(tree, nu.mp.Teleport)
    assert tree._payload["target"] == ("w", 7)


def test_a_dispatched_body_pickles():
    """Regression: ``nu.host`` mints its class where pickle cannot find it.

    Without the ``__module__`` fixup in ``dispatch`` this raises, and it
    raises in the middle of a run rather than at construct time, because the
    pickling happens when the Teleport fires.
    """
    body = slot_body(Slot(("w", 0), ("a_01",)))
    assert isinstance(pickle.loads(pickle.dumps(body)), nu.mp.Teleport)  # noqa: S301


@pytest.mark.parametrize("duration", [None, 0.5])
def test_the_tree_passes_the_law_gate(tmp_path, duration):
    tree, slots = runner_tree(
        ("a_00", "a_01", "a_02"),
        path=str(tmp_path / "db"),
        address="127.0.0.1:19999",
        warm=2,
        duration=duration,
    )
    validate(nu_compile(tree))
    assert len(slots) == 3


def test_an_empty_space_is_still_a_valid_tree(tmp_path):
    tree, slots = runner_tree(
        (),
        path=str(tmp_path / "db"),
        address="127.0.0.1:19999",
        warm=2,
    )
    validate(nu_compile(tree))
    assert [s.apps for s in slots] == [(), ()]
