"""System planes in tests: found by key, and their own programs run as their cells run them.

A system plane's id is minted, so a test asks for it by key. A program that
reads its own plane bare (``nuspace.at.plane``) runs inside a cell run; a
test runs it with :class:`~nuspace.places.Here` bound to that plane.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nuspace
from nuspace.places import inside
from nuspace.web.home import indexer
from nuspace.web.planes import ensure_indexer


if TYPE_CHECKING:
    import nu


async def keyed(store, key: str) -> str:
    """The id of the plane holding ``key``, ``""`` when none does."""
    return await store.read(nuspace.plane.keyed(key))


async def as_indexer(store, term: nu.Nu) -> object:
    """``term`` run as the home indexer's cell runs it: its plane made where missing, Here bound."""
    await store.run(ensure_indexer())
    return await store.run(inside(term, plane=await keyed(store, indexer.KEY)))


async def catch_up(store, **kwargs: int) -> None:
    """One indexer pass, as its cell runs it. ``kwargs``: :func:`~nuspace.web.home.indexer.catch_up`'s."""
    await as_indexer(store, indexer.catch_up(**kwargs))
