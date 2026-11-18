"""Navigators: a store's root shape bound to a kv navigator, whatever the backend.

kv refs find their navigator by the root shape they hang from, so binding
a store is binding its root. The backend is a parameter: the caller hands
a stack, any ``nustd.kv`` navigator preset with its own arguments filled
in, and this block puts it under the root's tag::

    stack = functools.partial(nustd.kv.sqlite_navigator_redis, path, redis_url=url)
    navigators.navigator(Space, stack)

Each process binds the same stores the same way: an assembly builds the
term once and hands it to its workers too, so a stack must pickle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    import nu


__all__ = ["Stack", "navigator"]


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
