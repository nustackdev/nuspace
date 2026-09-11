"""Wire handles: the surface Ref, and one Ref per op.

## SurfaceRef

The base for ``PagesRef`` / ``AppsRef`` / ``LensRef``. It exists for two
reasons, both of which are nu framework gaps rather than nuspace design:

- ``_wire_type_override``. ``_wire_type`` walks the MRO looking for an
  ancestor under ``nu.ui.refs``; an out-of-tree Ref has none, and the
  override is read off ``base.__dict__`` so it is not inherited. Every
  nuspace Ref therefore had to restate its own class name. Doing it in
  ``__init_subclass__`` stamps it once per subclass with the same result.
- ``slot(**kwargs)``. ``Ref.slot`` routes everything into mount *props*,
  which ride to the browser. A surface Ref is configured with a Shape
  *class* (``space_root``), which is python-side only and cannot be
  msgpacked. So it has to go through ``Slot(cls, props={}, **kwargs)``,
  which is what all three copies of ``slot()`` were doing by hand.

## Ops

One Ref per op, at ``<surface>.ops.<name>``. The browser notifies that
path and the server subscribes a handler to it, so the path *is* the
dispatch and the ``if op == ...`` chain has nothing left to ask.

Mount is not involved. The session dispatches a notify by looking the
frame's ref string up in its subscription table, and that table has no
relationship to the mount envelope. An op ref is never mounted, never
rendered, and never written to; it is an address the browser can name.

Consequences worth knowing:

- A notify to an op nobody subscribed runs nothing. ``Ops.stray()``
  covers the realistic case (the browser still notifying the bare
  surface path, i.e. a call site that missed the migration) by
  subscribing there and warning. Anything else -- a typo'd
  ``<surface>.ops.typpo``, say -- is caught one layer down:
  ``NuspaceSession._dispatch`` warns on any notify that matched no
  subscription at all. Neither changes routing; both just refuse to let
  it happen quietly.
- Bodies take named arguments, so a malformed frame is a ``TypeError``
  at call time rather than a silent ``payload.get(...) or ""``. That
  failure is caught in ``Perform``, once, instead of in a blanket
  ``except`` around the whole dispatch loop.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

import nu
import nu.ui
from nu.ui.core import Ref
from nuspace.web.refs.common.atoms import Perform


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["OpRef", "Ops", "SurfaceRef"]


log = logging.getLogger("nuspace.refs")


class SurfaceRef(Ref):
    """Base for a nuspace surface's wire handle.

    Payload is stamped once in ``__init__`` and never mutated after: Nu
    tree rewrites share the payload object, so a post-construction write
    bleeds across them.
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Name the browser factory after the class, unless the subclass
        # says otherwise. `_wire_type` reads `__dict__`, never `getattr`,
        # so this has to land on the subclass itself.
        if "_wire_type_override" not in cls.__dict__:
            cls._wire_type_override = cls.__name__

    @classmethod
    def slot(cls, **kwargs: object) -> Self:
        """Pin constructor kwargs (Shape classes, caps) onto the Slot."""
        return nu.Slot(cls, props={}, **kwargs)  # type: ignore[return-value]


class OpRef(Ref):
    """One op's address. Never mounts, never renders, never reads."""

    _wire_type_override = "OpRef"

    def changed(self) -> nu.Nu:
        """Subscribe to browser notifies on this op's path."""
        return nu.ui.Changed(self)


class Ops:
    """Builds the reactive handler for each op under one surface path."""

    def __init__(self, base: str) -> None:
        self._base = base

    def on(
        self,
        name: str,
        target: Any,  # noqa: ANN401 -- any Ref the op's effect lands on
        body: Callable[..., Any],
    ) -> nu.Nu:
        """One op: subscribe ``<base>.ops.<name>``, splat args into ``body``.

        ``target`` is the Ref the op writes -- ``Space.pages`` for the
        ones that change the document, the surface's own ui Ref for the
        ones whose only effect is a frame. Nu needs a Ref in a Command's
        mutation slot because that is the address the write lands at, and
        an op ref would be the wrong answer: nothing is ever written to
        an op ref.
        """
        ref = OpRef(f"{self._base}.ops.{name}")
        # Per-op attrs key. ReactForever writes the notify payload into
        # ctx.attrs before running the body, and every branch of the
        # surface program shares one ctx, so a shared key would let two
        # ops racing on the same tick read each other's arguments.
        key = f"nuspace.args.{name}"
        return nu.ReactForever(
            ref.changed(),
            Perform(target, body, args=key, splat=True, label=name),
            changed_key=key,
        )

    def stray(self, target: Any) -> nu.Nu:  # noqa: ANN401 -- any Ref
        """Warn on a notify to the bare surface path.

        Nothing should arrive here once every call site names an op. When
        one does, this is what says so instead of the frame vanishing.
        """
        ref = OpRef(self._base)
        key = "nuspace.args.stray"

        async def stray(payload: object) -> None:
            log.warning(
                "nuspace: notify on %s with no op (payload %r); "
                "the browser should name %s.ops.<op>",
                self._base,
                payload,
                self._base,
            )

        return nu.ReactForever(
            ref.changed(),
            Perform(target, stray, args=key, splat=False, label="stray"),
            changed_key=key,
        )
