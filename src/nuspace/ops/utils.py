"""Helpers the ops share.

Helpers are not concepts, so they sit in one file rather than in a module of
their own. Nothing here knows what a Plane or a Cell is.
"""

from __future__ import annotations

import itertools
import time
import uuid
from typing import TYPE_CHECKING

import nu
import nustd.kv


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.shapes import Space


__all__ = [
    "atomic",
    "flag",
    "keep_order",
    "mint_ordered_id",
    "text",
]


_ORDER_COUNTER = itertools.count()


def mint_ordered_id(prefix: str) -> str:
    """A time ordered id like ``p_<12 hex ms>_<4 hex seq>_<4 hex rand>``.

    A container is a dict listed sorted by key, so an id that sorts by the
    moment it was minted gives creation order with nothing storing it.

    Args:
        prefix: what the id starts with. ``p`` for a Plane, ``c`` for a Cell.
    """
    stamp = format(int(time.time() * 1000), "012x")
    # The counter separates two ids minted in the same millisecond; the random
    # tail keeps two processes apart, where the counter restarts from zero.
    seq = format(next(_ORDER_COUNTER) % 0x10000, "04x")
    return f"{prefix}_{stamp}_{seq}_{uuid.uuid4().hex[:4]}"


def atomic(body: nu.Nu, root: type[Space]) -> nu.Nu:
    """``body`` as one commit, so nothing ever observes half of it.

    Every write op goes through here. Without it the automatic pass brackets
    each branch of a Sequential separately and a multi field write lands as
    several commits, one notification each. A Cell whose key appears before
    its program does is a Cell the fold starts with nothing to run.
    """
    return nustd.kv.Transaction(body, scope=root)


def text(ref: nu.Nu, default: nu.StrArg = "") -> nu.Nu:
    """``ref`` as a string, ``default`` where nothing was written.

    An unwritten leaf reads EMPTY and every Query touching EMPTY collapses to
    INVALID, so a value on its way out of the store needs a floor.
    """
    return nu.If(ref.exists(), nu.ToStr(ref), nu.Str(default))


def flag(ref: nu.Nu, default: nu.BoolArg) -> nu.Nu:
    """``ref`` as a bool, ``default`` where nothing was written."""
    return nu.If(ref.exists(), nu.ToBool(ref), nu.Bool(default))


def keep_order(
    current: nu.Nu,
    wanted: Sequence[nu.StrArg] | nu.Nu,
    member: nu.Nu,
    *,
    item: str,
) -> nu.Nu:
    """Rewrite ``current`` as ``wanted``, members only, then whatever was left.

    Args:
        current: the list ref being reordered.
        wanted: the ids to put first, in the order given. A python sequence
            fixes the order while the tree is built; a ``nu.Nu`` yielding a
            list reads it while the tree runs, which is what a browser event
            carrying an order hands in.
        member: the collection that decides whether an id is real.
        item: the attr name the filters bind the current element under.
            Parallel arms share one ``ctx.attrs``, so every caller names its
            own.
    """
    at = nu.AnyAttrRef(item)
    listed = nu.List(wanted) if isinstance(wanted, nu.Nu) else nu.List.of(*wanted)
    kept = nu.List(nu.Collect(nu.Filter(listed, member.contains(at), key=item)))
    # Anything the caller left out keeps its place, after the ids that were
    # named, so a partial order is a move rather than a truncation.
    rest = nu.List(nu.Collect(nu.Filter(nu.list(current), nu.Not(listed.contains(at)), key=item)))
    return current.set(kept + rest)
