"""Dispatching a run: its record read, its envs built, its body shipped.

The one place a run crosses into a worker. It happens in the host, because
the host holds the pool and the env factories: specs are resolved here
(D2), the wraps applied here, and what crosses is plain Nu.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
import nustd.mp_pool
from nu.engine.structure import Declared
from nu.lang import Command
from nuspace.ops import CELL_ATTR, PLANE_ATTR, RUN_ATTR
from nuspace.ops.utils import or_else, text
from nuspace.shapes import Space
from nustd.mp_pool.interactions import _require_pool

from .body import build_body
from .envs import KernelConfig, KernelConfigRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["DispatchRun"]


class DispatchRun(Command):
    """Ship run ``run_id``'s body to pool worker ``wid``. Returns once the worker has it.

    Reads the run's plane, cell and env specs through a snapshot, resolves
    the specs through the :class:`~.envs.KernelConfig` on the context (none
    bound resolves nothing but refuses any spec), builds the body with
    :func:`~.body.build_body` and dispatches it.

    The dispatch carries the run's ids as attrs, which also gives the body
    a context copy of its own in the worker: bodies sharing a worker do not
    share attrs.

    Args:
        run_id: the run's store id, any ``StrArg``.
        wid: the pool's worker id, any ``IntArg``.

    Raises:
        UnknownEnvError: a spec names no registered env.
        WorkerGone: the worker died before it took the body.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, run_id: nu.StrArg, wid: nu.IntArg) -> None:
        row = Space.kernel.runs[run_id]
        record = nustd.kv.Snapshot(
            nu.Dict.of(plane=text(row.plane), cell=text(row.cell), envs=or_else(row.envs, [])),
            scope=Space,
        )
        super().__init__(nustd.mp_pool.PoolRef(), run_id, wid, record, KernelConfigRef())

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            msg = "DispatchRun runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> None:
            pool = _require_pool(await children[0](rt))
            run_id = await children[1](rt)
            wid = await children[2](rt)
            record = await children[3](rt)
            config = await children[4](rt)
            if not isinstance(config, KernelConfig):
                config = KernelConfig()
            plane, cell = record["plane"], record["cell"]
            body = build_body(run_id, plane, cell, config.resolve(record["envs"]))
            attrs = {PLANE_ATTR: plane, CELL_ATTR: cell, RUN_ATTR: run_id}
            await pool.adispatch(wid, body, attrs=attrs)

        return athunk
