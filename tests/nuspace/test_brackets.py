"""The brackets: ``nuspace.atomic`` and ``nuspace.bracketed``."""

from __future__ import annotations

import pytest

import nu
import nuspace
import nustd.kv
from nuspace.places import inside
from nuspace.shapes import Space


STORES = ("memory", "sqlite")

at = nuspace.at


class Counter(nu.Shape):
    value = nustd.kv.IntRef.slot()


def test_atomic_is_the_kv_bracket():
    assert nuspace.atomic is nustd.kv.atomic


def test_atomic_refuses_a_term_writing_two_stores():
    with pytest.raises(nustd.kv.BracketError):
        nuspace.atomic(nuspace.plane.rename("p", "x") >> at.space.state(Counter).value.set(1))


async def test_bracketed_brackets_each_step_on_its_store(store):
    """A flow writing Space then State: one commit each, the State write reading Space."""
    await store.run(
        nuspace.atomic(
            nuspace.plane.add("p", backend="async") >> nuspace.cell.add("p", "s", id="c1")
        )
    )
    mine = nuspace.here(Counter).value
    term = nuspace.cell.rename("c1", "Named") >> mine.set(nu.Len(Space.cells["c1"].name))
    await store.run(inside(nuspace.bracketed(term), plane="p", cell="c1"))
    assert await store.read(at.cell(id="c1").state(Counter).value) == 5
    assert await store.read(Space.cells["c1"].name) == "Named"


def test_bracketed_keeps_a_bracket_already_there_and_brackets_a_loop_per_step():
    op = nuspace.atomic(nuspace.plane.rename("p", "x"))
    assert nuspace.bracketed(op) is op
    loop = nu.ForeverDo(nu.DelayedDo(1.0, at.space.state(Counter).value.set(1)))
    assert isinstance(nuspace.bracketed(loop), nu.ForeverDo)
