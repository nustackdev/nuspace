"""The atoms a nuspace surface is written in.

Three of them, and they are the only place python runs inside a surface
program. Everything above them is composition: ``>>``, ``|``,
``nu.ForeverDo``, ``nu.ReactForever``, ``nu.ui.Write``.

``Payload`` yields a wire payload. ``Perform`` runs one interaction. The
split matters: shipping is ``nu.ui.Write(ref, Payload(fn))``, so the
frame-building half is nu's and only the computing half is ours.
``Perform`` is what an op body hangs off, and what the boot steps are.

Why python at all: a nuspace interaction addresses a page by a *runtime*
path (``root.pages.pages["p_a"].pages["p_b"].sections``). Nu has no term
for "descend a Shape by a list of ids computed at run time", so the
descent, and therefore the kv call it builds, lives in a python body. If
that term ever exists, these two atoms get thinner and nothing above them
changes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from nu.engine.structure import Declared
from nu.lang import Command, ScalarQuery


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime
    from nu.ui.core import Ref


__all__ = ["AsyncOnly", "Payload", "Perform"]


log = logging.getLogger("nuspace.refs")


class AsyncOnly:
    """Sync ``_compile`` that refuses, for atoms that only have an async path.

    Mix in front of the Nu kind. Six copies of this thunk existed across
    ``refs/``; a surface is a websocket, so none of them will ever have a
    sync path worth writing.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        name = type(self).__name__

        def thunk(rt: Runtime) -> None:
            raise RuntimeError(f"{name} is async-only; use nu.arun")

        return thunk


class Payload(AsyncOnly, ScalarQuery):
    """Yields one server-computed wire payload.

    The value slot of ``nu.ui.Write``. The body is an async python
    callable taking nothing and returning whatever should ride in the
    frame -- typically a dict the browser slice dispatches on.

    A body that raises is logged and yields ``None``; the frame still
    ships and the browser ignores it. That keeps one bad read from
    killing the loop the Payload sits in, which is a ``ForeverDo`` that
    nothing restarts.
    """

    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, body: Callable[[], Any], *, label: str = "") -> None:
        super().__init__()
        self._payload["nuspace_body"] = body
        self._payload["nuspace_label"] = label or getattr(body, "__name__", "payload")

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        body: Callable[[], Any] = self._payload["nuspace_body"]
        label: str = self._payload["nuspace_label"]

        async def athunk(rt: Runtime) -> Any:  # noqa: ANN401 -- payload is opaque
            try:
                return await body()
            except Exception:
                log.warning("nuspace payload %s failed", label, exc_info=True)
                return None

        return athunk


class Perform(AsyncOnly, Command):
    """Run one interaction body against the Ref its effect lands on.

    Slot 0 is that Ref and the only mutation slot, so the effect the atom
    carries is addressed: a page op names ``Space.pages``, a shipping op
    names the surface's own ui Ref. Slot 0 is never evaluated -- naming
    where a write goes is not reading what is there.

    ``args`` names a ``ctx.attrs`` key, which is how ``React`` hands a
    body the thing that woke it:

    - ``args=None``            -- ``await body()``
    - ``args="k", splat=True`` -- ``await body(**attrs["k"])``, so an op
      declares its arguments in its signature instead of digging them out
      of a payload dict
    - ``args="k", splat=False`` -- ``await body(attrs["k"])``, for a kv
      change whose key is a tuple

    Every failure is caught here. A malformed frame raises ``TypeError``
    at splat time and a kv read can raise anything; either one escaping
    would unwind ``nu.arun`` and take the websocket with it.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(
        self,
        ref: Ref,
        body: Callable[..., Any],
        *,
        args: str | None = None,
        splat: bool = True,
        label: str = "",
    ) -> None:
        super().__init__(ref)
        self._payload["nuspace_body"] = body
        self._payload["nuspace_args"] = args
        self._payload["nuspace_splat"] = splat
        self._payload["nuspace_label"] = label or getattr(body, "__name__", "perform")

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        body: Callable[..., Any] = self._payload["nuspace_body"]
        args: str | None = self._payload["nuspace_args"]
        splat: bool = self._payload["nuspace_splat"]
        label: str = self._payload["nuspace_label"]

        async def athunk(rt: Runtime) -> None:
            try:
                if args is None:
                    await body()
                    return
                value = rt.ctx.attrs.get(args)
                if splat:
                    if not isinstance(value, dict):
                        log.warning("nuspace op %s got a non-dict frame: %r", label, value)
                        return
                    await body(**{str(k): v for k, v in value.items()})
                    return
                await body(value)
            except Exception:
                log.warning("nuspace interaction %s failed", label, exc_info=True)

        return athunk
