"""Nu interactions nuspace needs and nu does not have yet. Generic: nothing here knows a plane.

- :class:`MintId`: a fresh time ordered id, minted each time it evaluates.
- :class:`IsSlug`: whether a key is spelled in slug chars.
- :class:`Require`: a value, or a raise when a condition does not hold. The
  query form of ``IfDo(check, Raise)``, for a read that must yield.

Each is hand written rather than ``nu.host``, so a term holding it pickles.
"""

from __future__ import annotations

import itertools
import re
import time
import uuid
from typing import TYPE_CHECKING

from nu.lang import ScalarQuery, is_null


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu
    from nu.lang.runtime import Runtime


__all__ = ["SLUG", "IsSlug", "MintId", "Require", "is_slug", "mint_ordered_id"]


_ORDER_COUNTER = itertools.count()

#: A key's spelling: lowercase letters, digits, ``_`` and ``-``, one at least. No ``/``.
SLUG = re.compile(r"[a-z0-9_-]+")


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


def is_slug(key: object) -> bool:
    """Whether ``key`` is a str spelled in slug chars (:data:`SLUG`)."""
    return isinstance(key, str) and SLUG.fullmatch(key) is not None


class MintId(ScalarQuery):
    """A fresh :func:`mint_ordered_id`, minted each time it is evaluated.

    Args:
        prefix: The id's prefix.

    Yields:
        The id, a str. NULL when the prefix is NULL.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (prefix,) = children

        def thunk(rt: Runtime) -> object:
            p = prefix(rt)
            return p if is_null(p) else mint_ordered_id(p)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (prefix,) = children

        async def athunk(rt: Runtime) -> object:
            p = await prefix(rt)
            return p if is_null(p) else mint_ordered_id(p)

        return athunk


class IsSlug(ScalarQuery):
    """Whether a key is spelled in slug chars (:func:`is_slug`).

    Args:
        key: The key, any term.

    Yields:
        A bool. False for NULL or anything that is not a str.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (key,) = children
        return lambda rt: is_slug(key(rt))

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (key,) = children

        async def athunk(rt: Runtime) -> object:
            return is_slug(await key(rt))

        return athunk


class Require(ScalarQuery):
    """``value`` when ``cond`` holds, else raise ``exc_cls(msg)``.

    ``Raise`` is a flow, so it cannot sit where a value goes. A read that
    must refuse (eg the title of a plane that is not there) yields through
    this instead. ``value`` is read only when ``cond`` holds, ``msg`` only
    when it does not.

    Args:
        cond: What must hold. NULL counts as not holding.
        value: What it yields when it does.
        msg: The error's message, any term.
        exc_cls: The error raised.

    Example:
        Require(Space.planes.contains(p), Space.planes[p].name, "no plane", exc_cls=Missing)
    """

    def __init__(
        self, cond: nu.Nu, value: object, msg: object, *, exc_cls: type[BaseException]
    ) -> None:
        super().__init__(cond, value, msg)
        self._payload["exc_cls"] = exc_cls

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        cond, value, msg = children
        exc_cls = self._payload["exc_cls"]

        def thunk(rt: Runtime) -> object:
            if cond(rt):
                return value(rt)
            raise exc_cls(msg(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        cond, value, msg = children
        exc_cls = self._payload["exc_cls"]

        async def athunk(rt: Runtime) -> object:
            if await cond(rt):
                return await value(rt)
            raise exc_cls(await msg(rt))

        return athunk
