"""The navigators block: a store bound to one stack, or split across several by top-level slot.

Space split across two sqlite files, ``planes`` and ``cells`` in one, the
rest in the other, and ops run through ``nuspace.atomic`` as anywhere.
Each file is then read on its own: it holds its slots and nothing else.
It proves the block takes a sharded store; no assembly ships one.
"""

from __future__ import annotations

import asyncio
import functools
import pickle

import pytest

import nu
import nuspace
import nustd.kv
from nuspace.kernel import init_live
from nuspace.shapes import ROOT, Space
from nuspace.shapes.stores import init_space
from nuspace.space.blocks import navigators
from nuspace.space.blocks.navigators import Shard


def _split(near: str, rest: str) -> nu.With:
    return navigators.sharded(
        Space,
        [
            Shard(functools.partial(nustd.kv.sqlite_navigator, near), slots=("planes", "cells")),
            Shard(functools.partial(nustd.kv.sqlite_navigator, rest)),
        ],
    )


def _run(bound: nu.With, term: nu.Nu) -> object:
    value, _ = asyncio.run(nu.arun(nu.With(bound, body=term)))
    return value


def _alone(file: str, term: nu.Nu) -> object:
    """``term`` read from one file, bound plain as the whole of Space."""
    return _run(
        navigators.navigator(Space, functools.partial(nustd.kv.sqlite_navigator, file)), term
    )


def test_a_store_split_by_top_level_slot_keeps_each_slot_in_its_file(tmp_path):
    near, rest = str(tmp_path / "near.db"), str(tmp_path / "rest.db")
    bound = _split(near, rest)
    _run(bound, nuspace.atomic(init_space()))
    _run(bound, nuspace.atomic(init_live()))
    _run(bound, nuspace.atomic(nuspace.plane.add("p", key="team", backend="async")))
    _run(bound, nuspace.atomic(nuspace.cell.add("p", "print(1)", id="c1")))

    # Read through the split, as any op does.
    assert _run(bound, nuspace.atomic(Space.planes["p"].key)) == "team"
    assert _run(bound, nuspace.atomic(Space.indexes.plane_keys["team"])) == "p"
    assert "p" in _run(bound, nuspace.atomic(nu.list(Space.planes[ROOT].children.keys())))

    # Each file holds its own slots only.
    has = Space.planes["p"].exists(), Space.cells["c1"].exists()
    keyed = Space.indexes.plane_keys.exists(), Space.info.format.exists()
    assert _alone(near, nuspace.atomic(nu.List.of(*has, *keyed))) == [True, True, False, False]
    assert _alone(rest, nuspace.atomic(nu.List.of(*has, *keyed))) == [False, False, True, True]


def test_a_split_pickles_for_the_workers(tmp_path):
    bound = _split(str(tmp_path / "a.db"), str(tmp_path / "b.db"))
    pickle.loads(pickle.dumps(bound))  # noqa: S301 -- our own term


def test_a_split_needs_exactly_one_shard_for_the_rest(tmp_path):
    stack = functools.partial(nustd.kv.sqlite_navigator, str(tmp_path / "a.db"))
    with pytest.raises(ValueError, match="exactly one shard keeps the rest"):
        navigators.sharded(Space, [Shard(stack, ("planes",))])
    with pytest.raises(ValueError, match="kept by two shards"):
        navigators.sharded(
            Space, [Shard(stack, ("planes",)), Shard(stack, ("planes",)), Shard(stack)]
        )
