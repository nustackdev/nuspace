"""``AppsRunner`` -- the node that gives apps a lifetime.

One line in the space's own tree::

    body = auto_flow_atomic(seed, scope=MySpace) >> (
        AppsRunner(MySpace) | nu.ForeverDo(nu.Delay(3600.0))
    )

That is the whole mount. It is deliberately *not* in the per-connection
ui tree, and that placement is the entire point of the apps pillar:

- The ui tree (``PagesDriver | LensDriver | AppsDriver``) is instantiated
  once per websocket session and torn down on disconnect.
- The space body is instantiated once, at boot, and lives until the
  process ends.

Apps run always, so they run here.

``AppsRunner`` must sit **outside** any ``auto_flow_atomic`` bracket. It
does not touch refs itself; it drives a supervisor that opens its own
snapshot per app, exactly as ``PagesDriver`` does. Nesting it inside an
outer atomic would put every app's whole lifetime inside one snapshot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nu.engine.structure import Declared
from nu.lang import Control

from .runtime import AppsRuntime, install_runtime


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nu.lang.runtime import Runtime


__all__ = ["AppsRunner"]


class AppsRunner(Control):
    """Own the apps supervisor for the life of the space rooted at ``root``.

    Takes the root Shape *class* rather than a ref, because there is
    nothing to address: the runner supervises the whole ``apps`` slot,
    and the class is also the registry key drivers look the runtime up
    by and the scope every app's tree is flowed against.
    """

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, root: type[Shape]) -> None:
        super().__init__()
        self._payload["apps_root"] = root

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("AppsRunner is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        root: type[Shape] = self._payload["apps_root"]

        async def athunk(rt: Runtime) -> None:
            runtime = AppsRuntime(rt.ctx, root)
            # The runtime is published for the whole reconcile loop and
            # withdrawn when it ends, so a driver can never hold a handle
            # on a supervisor whose loop has stopped.
            with install_runtime(root, runtime):
                await runtime.arun()

        return athunk
