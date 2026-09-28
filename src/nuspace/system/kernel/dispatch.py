"""Running a cell run: its record read, its envs built, its body run by the backend to its end.

The one place a cell run crosses into a backend. It happens in the host,
because the host holds the backends and the env factories: specs are
resolved here (D2), the wraps applied here, and what crosses is plain Nu.
Where it lands was decided before, by the backend's ``place``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nu.engine.structure import Declared
from nu.lang import ScalarAction
from nuspace.ops import CELL_ATTR, CELL_RUN_ATTR, PLANE_ATTR, RUN_ATTR
from nuspace.ops.utils import or_else, text
from nuspace.shapes import Space
from nuspace.system.backends import BackendRef, require_backend

from .body import build_body
from .envs import KernelConfig, KernelConfigRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["RunCell"]


class RunCell(ScalarAction):
    """Run cell run ``cell_run_id``'s body on the plane run's backend. Returns once it has ended.

    Reads the plane run's plane and env specs and the cell run's cell
    through a snapshot, resolves the specs through the
    :class:`~.envs.KernelConfig` on the context (none bound resolves
    nothing but refuses any spec), builds the body with
    :func:`~.body.build_body` and awaits it through the backend's
    :meth:`~nuspace.system.backends.Backend.arun`. Cancelled, the backend
    cancels the body where it runs.

    The request carries the ids as attrs, which also gives the body a
    context copy of its own on the worker: bodies sharing a worker do not
    share attrs.

    Args:
        backend: The backend's registered name, any ``StrArg``.
        run_id: The plane run's store id.
        cell_run_id: The cell run's store id, placed already.

    Yields:
        ``""`` when the body ran to its end, or why its worker was lost.

    Raises:
        UnknownEnvError: A spec names no registered env.
        UnknownBackendError: No backend is registered under ``backend``.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, backend: nu.StrArg, run_id: nu.StrArg, cell_run_id: nu.StrArg) -> None:
        row = Space.kernel.runs[run_id]
        record = nustd.kv.Snapshot(
            nu.Dict.of(
                plane=text(row.plane),
                cell=text(row.cells[cell_run_id].cell),
                envs=or_else(row.envs, []),
            ),
            scope=Space,
        )
        super().__init__(BackendRef(backend), run_id, cell_run_id, record, KernelConfigRef())

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> str:
            msg = "RunCell runs on a loop; use arun"
            raise RuntimeError(msg)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> str:
            backend = require_backend(await children[0](rt))
            run_id = await children[1](rt)
            cell_run_id = await children[2](rt)
            record = await children[3](rt)
            config = await children[4](rt)
            if not isinstance(config, KernelConfig):
                config = KernelConfig()
            plane, cell = record["plane"], record["cell"]
            envs = config.resolve(record["envs"])
            body = build_body(run_id, cell_run_id, plane, cell, envs)
            attrs = {
                PLANE_ATTR: plane,
                CELL_ATTR: cell,
                RUN_ATTR: run_id,
                CELL_RUN_ATTR: cell_run_id,
            }
            return await backend.arun(run_id, cell_run_id, body, attrs)

        return athunk
