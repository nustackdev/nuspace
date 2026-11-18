"""Guarded: steps run in order before a body, the body's value kept. And the refusal such a step usually is.

An entry point checks and prepares before it runs: the space is
initialized, what it runs on is up, its dirs are made. Those are flow, and
a flow yields nothing, so ``check >> body`` would drop what the body
yields (and a Query body does not fit a Flow at all). :class:`Guarded` is
the bracket for it: the steps, then the body, the body's value out.

:func:`refused` is the check itself: a query saying why not, or ``""``
when fine, read once, raised when it says something.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.errors import Refused


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Guarded", "refused"]


class Guarded(nu.Bracket):
    """``steps`` run in order, then ``body``. Yields what ``body`` yields.

    A bracket and not a flow, so the body keeps its value and its
    cardinality: a scalar, a stream, or nothing.

    It cannot sit in a ``nu.With``'s bracket list: ``With`` enters only a
    bracket's open and close, and Guarded has none. Wrap the With instead:
    ``Guarded(nu.With(..., body=b), check, ...)``.

    Args:
        body: What runs once every step is done.
        *steps: Run first, in order: checks, refusals, writes.
    """

    def __init__(self, body: nu.Nu, *steps: nu.Nu) -> None:
        super().__init__(body, *steps)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        body, steps = children[0], children[1:]

        def thunk(rt: Runtime) -> object:
            for step in steps:
                step(rt)
            return body(rt)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        body, steps = children[0], children[1:]

        async def athunk(rt: Runtime) -> object:
            for step in steps:
                await step(rt)
            return await body(rt)

        return athunk


def refused(why: nu.Nu, exc_cls: type[Exception] = Refused) -> nu.Nu:
    """``exc_cls(why)`` raised when the query ``why`` says something, nothing when it says ``""``.

    ``why`` is read once, held in a let, so the check and the message come
    from one look.

    Args:
        why: A query yielding the refusal, ``""`` when there is none.
        exc_cls: What is raised: ``Refused``, or ``Missing`` for no space at all.
    """
    return nu.let(why, lambda said: nu.IfDo(said, nu.Raise(said, exc_cls=exc_cls)))
