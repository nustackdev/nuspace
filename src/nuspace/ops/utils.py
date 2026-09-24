"""Helpers the ops share: the bracket, run time ids, yielding after writes.

Nothing here knows what a plane or a cell is.
"""

from __future__ import annotations

import itertools
import time
import uuid
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nu.engine.structure import Declared
from nu.lang import ScalarAction, ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID
from nuspace.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.lang.runtime import Runtime


__all__ = [
    "MintId",
    "PopAttr",
    "as_list",
    "atomic",
    "binding",
    "flag",
    "fresh",
    "keep_order",
    "mint_ordered_id",
    "minting",
    "or_else",
    "text",
    "then",
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
    """An attr name no other op term uses.

    Parallel arms share one ``ctx.attrs``, so every binding an op makes is
    named apart at build time. The name is fixed per term, the value per run.
    """
    return f"_nsop_{tag}_{next(_FRESH)}"


class MintId(ScalarQuery):
    """A fresh :func:`mint_ordered_id`, minted each time it is evaluated.

    Hand written rather than ``nu.host`` so a term holding it pickles.

    Args:
        prefix: The id's prefix.

    Yields:
        The id, a str. INVALID when the prefix is a sentinel.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (prefix,) = children

        def thunk(rt: Runtime) -> object:
            p = prefix(rt)
            if p is EMPTY or p is INVALID:
                return INVALID
            return mint_ordered_id(p)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (prefix,) = children

        async def athunk(rt: Runtime) -> object:
            p = await prefix(rt)
            if p is EMPTY or p is INVALID:
                return INVALID
            return mint_ordered_id(p)

        return athunk


class PopAttr(ScalarAction):
    """Unbinds an attr and yields what it held.

    What lets an op write and then yield: a Flow yields nothing and a bare
    read is a Query, which a ``>>`` refuses. Ending on this Action keeps the
    whole op an Action, so it chains and it binds.

    Args:
        name: The attr to take.

    Yields:
        The value bound under ``name``, EMPTY when nothing was.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, name: str) -> None:
        super().__init__(nu.AnyAttrRef(name))
        self._payload = {"name": name}

    def _take(self, rt: Runtime, value: object) -> object:
        name = self._payload["name"]
        attrs = rt.ctx.attrs
        if name in attrs:
            del attrs[name]
        return value

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (ref,) = children

        def thunk(rt: Runtime) -> object:
            return self._take(rt, ref(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (ref,) = children

        async def athunk(rt: Runtime) -> object:
            return self._take(rt, await ref(rt))

        return athunk


def atomic(body: nu.Nu) -> nu.Nu:
    """``body`` as one commit against the Space store, retried on conflict.

    Every write op goes through here. Without it the automatic pass brackets
    each branch of a Sequential apart and one op lands as several commits.
    Ops are called from many processes at once (services on workers, the
    host), so a lost commit is re-run against fresh state.

    Brackets do not merge: an op inside another op's bracket opens its own.
    Composite ops are built from unbracketed parts for that reason.
    """
    return nustd.kv.RetryOnConflict(nustd.kv.Transaction(body, scope=Space))


def then(effect: nu.Nu, name: str) -> nu.Nu:
    """Run ``effect``, then take and yield the attr ``name``. An Action."""
    return nu.Let(fresh("then"), effect, PopAttr(name))


def binding(
    value: nu.Nu,
    build: Callable[[str], nu.Nu],
    *,
    tag: str = "bind",
) -> nu.Nu:
    """Bind ``value`` under a fresh attr, run ``build(name)``, yield the binding.

    ``build`` gets the attr name and returns the writes. The value is
    evaluated once, before the writes, so a check made here sees the store
    as it was.
    """
    name = fresh(tag)
    return nu.Let(name, value, then(build(name), name))


def minting(prefix: str, build: Callable[[nu.StrAttrRef], nu.Nu]) -> nu.Nu:
    """Mint an id at evaluation time, run ``build(id_ref)``, yield the id.

    Minted when the term runs, not when it is built, so one term evaluated
    twice makes two things.
    """
    return binding(MintId(prefix), lambda name: build(nu.StrAttrRef(name)), tag=prefix)


def as_list(items: Sequence[nu.StrArg] | nu.Nu) -> nu.List:
    """A python sequence or a Nu term yielding a list, as a list term."""
    return nu.List(items) if isinstance(items, nu.Nu) else nu.List.of(*items)


def text(ref: nu.Nu, default: nu.StrArg = "") -> nu.Nu:
    """``ref`` as a str, ``default`` where nothing was written.

    An unwritten leaf reads EMPTY and a Query touching EMPTY is INVALID, so a
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
    at = nu.AnyAttrRef(item)
    listed = as_list(wanted)
    kept = nu.List(nu.Collect(nu.Filter(listed, member.contains(at), key=item)))
    # Ids left out keep their place after the named ones, so a partial order
    # is a move rather than a truncation.
    rest = nu.List(nu.Collect(nu.Filter(nu.list(current), nu.Not(listed.contains(at)), key=item)))
    return current.set(kept + rest)
