"""Navigators: a store's root shape bound to kv navigators, whatever the backend, sharded or not.

kv refs find their navigator by the root shape they hang from, so binding
a store is binding its root. The backend is a parameter: the caller hands
a stack, any ``nustd.kv`` navigator preset with its own arguments filled
in, and this block puts it under the root's tag::

    stack = functools.partial(nustd.kv.sqlite_navigator_redis, path, redis_url=url)
    navigators.navigator(Space, stack)

One store may also live on several stacks, split by top-level slot
(:func:`sharded`): each :class:`Shard` stands up its stack under a tag of
its own, and a navigator guarded by a predicate is bound at the root's
tag for each, so a ref reaches the shard holding its slot. ``atomic``
brackets every shard a body touches. The drivers never see the split.

Each process binds the same stores the same way: an assembly builds the
term once and hands it to its workers too, so every part here pickles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from virtuals import Navigator as BaseNavigator

import nu
from nustd.kv.fabrics import Navigator


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nu.lang.runtime import Context


__all__ = ["Shard", "Stack", "navigator", "sharded"]


class Stack(Protocol):
    """A kv stack: a ``nustd.kv`` navigator preset with all but its tags given."""

    def __call__(self, *, tags: tuple[object, ...]) -> nu.With:
        """The preset's bracket, every binding it makes under ``tags``."""
        ...


def navigator(root: type[nu.Shape], stack: Stack) -> nu.With:
    """``root`` bound to one kv stack: every ref under it reads and writes there.

    Args:
        root: The store's root shape, the tag its refs resolve under.
        stack: The backend, eg ``partial(nustd.kv.sqlite_navigator, path)``.
    """
    return stack(tags=(root,))


@dataclass(frozen=True)
class Shard:
    """One part of a sharded store: a stack and the top-level slots it holds.

    Attributes:
        stack: The backend of this part.
        slots: The root's top-level slots kept here, eg ``("planes", "cells")``.
            Empty keeps every slot no other shard names: exactly one shard
            of a store leaves it empty.
    """

    stack: Stack
    slots: tuple[str, ...] = ()


@dataclass(frozen=True)
class ShardTag:
    """The tag a shard's own stack is bound under, never one a ref carries."""

    root: type
    index: int


@dataclass(frozen=True)
class Holds:
    """The predicate of a shard's navigator: whether a ref's top-level slot is kept there.

    A plain value, not a closure, so the bindings pickle to workers.
    """

    slots: frozenset[str]
    others: frozenset[str]

    def __call__(self, *, site: tuple, path: tuple) -> bool:
        """``site[0]`` is the ref's top-level slot under the root."""
        top = site[0]
        return top in self.slots if self.slots else top not in self.others


class Routed(Navigator):
    """A shard's storage, bound again at the root's tag behind the shard's predicate.

    Args:
        via: The shard's tags: its own navigator is found there at setup.
    """

    def __init__(self, *, via: tuple[object, ...]) -> None:
        super().__init__(storage_tags=via)

    def setup(self, ctx: Context) -> None:
        """Take the storage of the shard's own navigator."""
        shard = ctx.fabrics.get(BaseNavigator, *self._storage_tags)
        BaseNavigator.__init__(self, shard.storage, self._root_view)
        self._opened = True


def sharded(
    root: type[nu.Shape], shards: Sequence[Shard], *, observer: Stack | None = None
) -> nu.With:
    """``root`` split across ``shards`` by top-level slot: each ref reads and writes its slot's shard.

    A ref with no path below the root (the root itself) has no shard: read
    and write its slots.

    Args:
        root: The store's root shape.
        shards: Its parts. Exactly one leaves ``slots`` empty, the rest.
        observer: The root's observer, for watches: one that hears every
            shard, eg ``partial(nustd.kv.redis_observer, url, channel)``
            when each shard's stack publishes on that channel. None binds
            none, and nothing under the root can be watched.

    Raises:
        ValueError: Not exactly one shard keeps the rest, or a slot is named twice.
    """
    named = [s for shard in shards for s in shard.slots]
    if sum(1 for shard in shards if not shard.slots) != 1:
        msg = f"sharding {root.__name__}: exactly one shard keeps the rest (empty slots)"
        raise ValueError(msg)
    if len(named) != len(set(named)):
        msg = f"sharding {root.__name__}: a slot is kept by two shards"
        raise ValueError(msg)
    others = frozenset(named)
    parts: list[nu.Nu] = []
    for i, shard in enumerate(shards):
        tag = ShardTag(root, i)
        holds = Holds(frozenset(shard.slots), frozenset() if shard.slots else others)
        parts.append(shard.stack(tags=(tag,)))
        parts.append(nu.Provide(Routed, {"via": (tag,)}, tags=(root,), predicate=holds))
    if observer is not None:
        parts.append(observer(tags=(root,)))
    return nu.With(*parts)
