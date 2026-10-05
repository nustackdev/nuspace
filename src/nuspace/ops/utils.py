"""Helpers the ops share: the bracket, run time ids, a total field read, a reorder.

Nothing here knows what a plane or a cell is.

The bracket rule. Nothing brackets a term for its author: a store read or
write with no bracket around it raises, and nothing autocommits. So whoever
touches a store brackets it, and every op, service and cell program keeps
to the same rule:

- **One short bracket per store, Space first.** A write is one commit to
  one store (:func:`atomic` or :func:`atomic_state`); a term writing both is
  a commit to each, Space then States. A read is one :func:`snapshot`.
- **What decides a write is read inside its bracket.** A check and the
  write it guards share one commit, so nothing lands between them.
- **A term argument that reads a store is read inside the bracket too**, or
  first, on its own, as ``nu.let(snapshot(...), ...)``, when the op uses it
  before its bracket opens.
- **No bracket is held across slow or open ended work:** another op (it
  opens its own, and two write brackets on one store never join), a wait or
  a subscription's body, a loaded program (``Eval``, ``LoadNu``), or a call
  out of the process. The work runs bare, its result is kept in a
  ``nu.let`` slot, and a short bracket after it writes what it came to.
- **Bare reads stay bare.** A read helper composes into any expression, so
  it brackets nothing and its caller wraps it.

Brackets never join: one opened inside another on the same store is a
second handle, and a second write one on SQLite is the same thread waiting
on its own lock.
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
    "atomic",
    "atomic_state",
    "field_str",
    "keep_order",
    "mint_ordered_id",
    "snapshot",
]


_ORDER_COUNTER = itertools.count()


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

    Every write op goes through here, around its whole body, so the reads
    that decide a write and the write land as one commit. Ops are called
    from many processes at once (services on workers, the host), so a lost
    commit is re-run against fresh state.

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


def field_str(row: nu.Nu, field: str) -> nu.Str:
    """One string field off a dict, a row or a browser event: ``""`` when absent.

    Total on purpose, so a field left out hands an op a string, not EMPTY.
    """
    return nu.str(nu.Dict(row).get_item(field, ""))


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
    listed = nu.List(wanted) if isinstance(wanted, nu.Nu) else nu.List.of(*wanted)
    kept = listed.iter().filter(lambda c: member.contains(c)).to_list()
    # Ids left out keep their place after the named ones, so a partial order
    # is a move rather than a truncation.
    rest = nu.list(current).iter().filter(lambda c: listed.contains(c).not_()).to_list()
    return current.set(kept + rest)
