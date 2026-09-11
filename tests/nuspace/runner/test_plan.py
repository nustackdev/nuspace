"""The pool plan: how many workers, and who goes where."""

from __future__ import annotations

import pytest

from nuspace.runner import Slot, plan


def test_warm_pool_with_no_apps():
    slots = plan((), warm=3)
    assert len(slots) == 3
    assert all(s.apps == () for s in slots)
    assert [s.tag for s in slots] == [("w", 0), ("w", 1), ("w", 2)]


def test_apps_fit_inside_the_warm_pool():
    slots = plan(("a", "b"), warm=4)
    assert len(slots) == 4
    assert slots[0] == Slot(("w", 0), ("a",))
    assert slots[1] == Slot(("w", 1), ("b",))
    assert slots[2].apps == ()
    assert slots[3].apps == ()


def test_pool_grows_past_warm():
    slots = plan(tuple(f"a{i}" for i in range(5)), warm=2)
    assert len(slots) == 5
    assert [s.apps for s in slots] == [("a0",), ("a1",), ("a2",), ("a3",), ("a4",)]


def test_per_worker_batches():
    slots = plan(("a", "b", "c", "d", "e"), warm=1, per_worker=2)
    assert [s.apps for s in slots] == [("a", "b"), ("c", "d"), ("e",)]


def test_per_worker_still_respects_warm():
    slots = plan(("a", "b"), warm=4, per_worker=2)
    assert len(slots) == 4
    assert slots[0].apps == ("a", "b")


@pytest.mark.parametrize(("warm", "per_worker"), [(-1, 1), (1, 0)])
def test_nonsense_is_refused(warm, per_worker):
    with pytest.raises(ValueError):
        plan(("a",), warm=warm, per_worker=per_worker)
