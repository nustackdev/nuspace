"""Helpers the ops share: the bracket, run time ids, reads with a floor.

Nothing here knows what a plane or a cell is.
"""

from __future__ import annotations

import itertools
import time
import uuid
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nu.lang.sentinels import EMPTY
from nuspace.shapes import Space, States


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.lang.runtime import Runtime


__all__ = [
    "MintId",
    "as_list",
    "atomic",
    "atomic_state",
    "flag",
    "fresh",
    "keep_order",
    "mint_ordered_id",
    "or_else",
    "snapshot",
    "text",
]


_ORDER_COUNTER = itertools.count()
_FRESH = itertools.count()


def mint_ordered_id(prefix: str) -> str:
    """A time ordered id like ``p_<12 hex ms>_<4 hex seq>_<4 hex rand>``.

    A container lists sorted by key, so ids that sort by the moment they were
    minted give creation order with nothing storing it.

    Args:
        prefix: What the id starts with, eg ``p`` for a plane.
    """
    stamp = format(int(time.time() * 1000), "012x")
    # The counter separates two ids in one millisecond, the random tail two
    # processes, where the counter restarts from zero.
    seq = format(next(_ORDER_COUNTER) % 0x10000, "04x")
    return f"{prefix}_{stamp}_{seq}_{uuid.uuid4().hex[:4]}"


def fresh(tag: str) -> str:
    """A name for a loop's item that no other op term uses.

    A loop binds its item in ``ctx.attrs`` for its body, shadowing any outer
    binding of the name. A term handed into the body from outside may read
    an outer loop's item, so every loop an op builds names its item apart.
    The name is fixed per term, the value per run.
    """
    return f"_nsop_{tag}_{next(_FRESH)}"


class MintId(ScalarQuery):
    """A fresh :func:`mint_ordered_id`, minted each time it is evaluated.

    Hand written rather than ``nu.host`` so a term holding it pickles.

    Args:
        prefix: The id's prefix.

    Yields:
        The id, a str. EMPTY when the prefix is EMPTY.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (prefix,) = children

        def thunk(rt: Runtime) -> object:
            p = prefix(rt)
            if p is EMPTY:
                return EMPTY
            return mint_ordered_id(p)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (prefix,) = children

        async def athunk(rt: Runtime) -> object:
            p = await prefix(rt)
            if p is EMPTY:
                return EMPTY
            return mint_ordered_id(p)

        return athunk


def atomic(body: nu.Nu) -> nu.Nu:
    """``body`` as one commit against the Space store, retried on conflict.

    Every write op goes through here. Without it the automatic pass brackets
    each branch of a Sequential apart and one op lands as several commits.
    Ops are called from many processes at once (services on workers, the
    host), so a lost commit is re-run against fresh state.

    Brackets do not merge: an op inside another op's bracket opens its own.
    Composite ops are built from unbracketed parts for that reason.

    Space only: States reads inside see a snapshot, opened only if one is
    made, and a States write has no transaction to go through and fails. An
    op that writes both is two commits, see :func:`atomic_state`.
    """
    snapped = nustd.kv.Snapshot(nustd.kv.Transaction(body, scope=Space), scope=States)
    return nustd.kv.RetryOnConflict(snapped)


def atomic_state(body: nu.Nu) -> nu.Nu:
    """``body`` as one commit against the States store, retried on conflict.

    :func:`atomic` for program state. Space reads inside see a snapshot,
    opened only if one is made, so a state write can ask about structure
    (eg whether the cell is there) without taking the Space store's lock.

    The two stores are two files: nothing commits both at once. An op that
    writes both commits Space first, then States, and never holds both
    write locks, so two processes writing both can never wait on each
    other. Structure first means a live plane or cell never points at state
    that is gone; what a crash between the two can leave is state nothing
    points at.
    """
    snapped = nustd.kv.Snapshot(nustd.kv.Transaction(body, scope=States), scope=Space)
    return nustd.kv.RetryOnConflict(snapped)


def snapshot(term: nu.Nu) -> nu.Nu:
    """``term`` read in a snapshot of both stores, Space and States.

    Each opens only if ``term`` reads it, so wrapping a read that touches
    one store costs nothing for the other.
    """
    return nustd.kv.Snapshot(nustd.kv.Snapshot(term, scope=States), scope=Space)


def as_list(items: Sequence[nu.StrArg] | nu.Nu) -> nu.List:
    """A python sequence or a Nu term yielding a list, as a list term."""
    return nu.List(items) if isinstance(items, nu.Nu) else nu.List.of(*items)


def text(ref: nu.Nu, default: nu.StrArg = "") -> nu.Nu:
    """``ref`` as a str, ``default`` where nothing was written.

    An unwritten leaf reads EMPTY and a Query touching EMPTY is EMPTY too, so a
    value on its way out of the store needs a floor.
    """
    return nu.If(ref.exists(), nu.ToStr(ref), nu.Str(default))


def flag(ref: nu.Nu, default: nu.BoolArg) -> nu.Nu:
    """``ref`` as a bool, ``default`` where nothing was written."""
    return nu.If(ref.exists(), nu.ToBool(ref), nu.Bool(default))


def or_else(ref: nu.Nu, default: object) -> nu.Nu:
    """``ref`` as it is, ``default`` where nothing was written."""
    return nu.If(ref.exists(), ref, nu.Literal(default))


def keep_order(
    current: nu.Nu,
    wanted: Sequence[nu.StrArg] | nu.Nu,
    member: nu.Nu,
) -> nu.Nu:
    """Rewrite ``current`` as ``wanted``, members only, then whatever was left.

    Args:
        current: The list ref being reordered.
        wanted: The ids to put first, in the order given. A python sequence
            or a Nu term yielding a list.
        member: The collection that decides whether an id is real.
    """
    item = fresh("order")
    at = nu.Attr(item)
    listed = as_list(wanted)
    kept = nu.List(nu.Collect(nu.Filter(listed, member.contains(at), key=item)))
    # Ids left out keep their place after the named ones, so a partial order
    # is a move rather than a truncation.
    rest = nu.List(nu.Collect(nu.Filter(nu.list(current), nu.Not(listed.contains(at)), key=item)))
    return current.set(kept + rest)
