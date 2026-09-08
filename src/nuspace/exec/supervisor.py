"""``Supervisor`` -- a page is a supervision group, a section is a worker.

The unit is the section, not the page. A page open acquires one warm
worker per section; each worker compiles its own source and drives its
own tree. That is what buys per-section restart, per-section error
isolation and per-section status, and it is why one section erroring
cannot take the page down.

**Teardown never blocks navigation.** Closing a page is bookkeeping
only: bump the generation, cancel the pumps, drop the routes, publish
``stopped``. The kill ladder for each worker runs detached in the
background. A worker that refuses to die is already forgotten, so it
cannot delay the next page, and any frame it still emits is dropped on
its stale generation.

Open, close and edit all serialize on one navigation lock, so two
generations of a page can never be live at the same time.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from nu.ui.core.protocol import Frame

from .handle import Timeouts, WorkerHandle
from .pool import WarmPool
from .protocol import (
    MSG_COMPILED,
    MSG_FAILED,
    MSG_INVALID,
    MSG_NOTIFY,
    MSG_READ,
    MSG_READ_ERR,
    MSG_READ_OK,
    MSG_RUN,
    MSG_RUNNING,
    MSG_SEND,
    MSG_START,
    MSG_STOPPED,
    MSG_SUBSCRIBE,
    MSG_UNSUBSCRIBE,
)
from .status import SectionStatus, StatusEvent, StatusStream


if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence


__all__ = ["SectionSpec", "Supervisor", "UiHost"]


class UiHost(Protocol):
    """Where a worker's ui traffic goes on the server side.

    One implementation wraps the browser websocket session; the tests use
    a loopback. The supervisor itself knows nothing about browsers.
    """

    async def send(self, page_id: str, section_id: str, frame: Frame) -> None:
        """Ship a frame produced by a section."""
        ...

    async def aread(self, page_id: str, section_id: str, path: str) -> Any:  # noqa: ANN401
        """Round-trip a read on behalf of a section."""
        ...


@dataclass(frozen=True)
class SectionSpec:
    """One section: an id and the python that evaluates to its tree."""

    id: str
    source: str
    prefix: str | None = None

    def mount_prefix(self) -> str:
        """Path prefix the section owns. Mounting is by prefix."""
        return self.prefix or f"sections.{self.id}"


@dataclass(eq=False)
class _Worker:
    """Supervisor-side record for one running section."""

    section_id: str
    page_id: str
    generation: int
    handle: WorkerHandle
    pump: asyncio.Task | None = None
    routes: set[str] = field(default_factory=set)


@dataclass
class _Page:
    """One generation of one open page."""

    page_id: str
    generation: int
    specs: dict[str, SectionSpec] = field(default_factory=dict)
    workers: dict[str, _Worker] = field(default_factory=dict)
    statuses: dict[str, SectionStatus] = field(default_factory=dict)


class Supervisor:
    """Runs section trees out of process, one worker per section."""

    def __init__(
        self,
        host: UiHost | None = None,
        *,
        pool_size: int = 8,
        store: dict[str, Any] | None = None,
        timeouts: Timeouts | None = None,
        compile_timeout: float = 5.0,
    ) -> None:
        self._host = host
        self._timeouts = timeouts or Timeouts()
        self._compile_timeout = compile_timeout
        self._pool = WarmPool(pool_size, timeouts=self._timeouts)
        self._store = dict(store or {"kind": "none"})
        self._pages: dict[str, _Page] = {}
        self._generations: dict[str, int] = {}
        self._routes: dict[str, set[_Worker]] = {}
        self._reaping: set[asyncio.Task] = set()
        self._tasks: set[asyncio.Task] = set()
        self._nav_lock = asyncio.Lock()
        self._closed = False
        self.stream = StatusStream()

    # -- lifecycle -----------------------------------------------------------

    async def astart(self) -> None:
        """Warm the pool. Page open is not instant until this returns."""
        await self._pool.astart()

    async def aclose(self) -> None:
        """Close every page, kill every worker, drain the reapers."""
        if self._closed:
            return
        self._closed = True
        async with self._nav_lock:
            for page_id in list(self._pages):
                await self._teardown(page_id, reason="stopped")
        await self._pool.aclose()
        if self._tasks:
            await asyncio.gather(*tuple(self._tasks), return_exceptions=True)
        await self.drain()
        self.stream.close()

    async def drain(self, timeout: float | None = None) -> None:
        """Await every in-flight kill ladder. Tests and shutdown only."""
        while self._reaping:
            pending = tuple(self._reaping)
            await asyncio.wait(pending, timeout=timeout)
            if timeout is not None:
                return

    async def __aenter__(self) -> Supervisor:
        await self.astart()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # -- pages ---------------------------------------------------------------

    async def prepare_page(self, page_id: str, specs: Sequence[SectionSpec]) -> int:
        """Tear down the old generation, compile the new one, run nothing.

        Every worker parks between compiling and running, so the caller
        gets the mount fields, ships them to the browser, and only then
        calls :meth:`launch_page`. A section can therefore never write to
        a slice the browser has not registered yet.

        Compilation is bounded by ``compile_timeout``: a section whose
        source wedges the worker leaves that section in ``starting`` and
        does not hold the rest of the page hostage.
        """
        if self._closed:
            raise RuntimeError("supervisor is closed")
        async with self._nav_lock:
            await self._teardown(page_id, reason="stopped")
            generation = self._generations.get(page_id, 0) + 1
            self._generations[page_id] = generation
            page = _Page(page_id=page_id, generation=generation)
            for spec in specs:
                page.specs[spec.id] = spec
                page.statuses[spec.id] = SectionStatus(spec.id, state="starting")
            self._pages[page_id] = page
            for spec in specs:
                self._publish(page, page.statuses[spec.id])
            await asyncio.gather(*(self._start_section(page, s) for s in specs))
            await self._await_compiled(page)
            return generation

    async def launch_page(self, page_id: str) -> None:
        """Release every compiled section of a page into its run."""
        page = self._pages.get(page_id)
        if page is None:
            return
        await asyncio.gather(
            *(rec.handle.send({"t": MSG_START}) for rec in page.workers.values()),
            return_exceptions=True,
        )

    async def open_page(self, page_id: str, specs: Sequence[SectionSpec]) -> int:
        """Prepare and launch in one call. Returns the generation.

        Any previous generation of the page is torn down first, under the
        same lock, so the two can never overlap.
        """
        generation = await self.prepare_page(page_id, specs)
        await self.launch_page(page_id)
        return generation

    async def close_page(self, page_id: str) -> None:
        """Stop every section on a page. Returns as soon as it is forgotten."""
        async with self._nav_lock:
            await self._teardown(page_id, reason="stopped")

    async def prepare_section(self, page_id: str, spec: SectionSpec) -> list[dict[str, Any]]:
        """Restart **only** this section, up to compiled. Returns its fields."""
        async with self._nav_lock:
            page = self._pages.get(page_id)
            if page is None:
                return []
            page.specs[spec.id] = spec
            self._stop_section(page, spec.id)
            page.statuses[spec.id] = SectionStatus(spec.id, state="starting")
            self._publish(page, page.statuses[spec.id])
            await self._start_section(page, spec)
            await self._await_compiled(page, sections=[spec.id])
            return list(page.statuses[spec.id].fields)

    async def launch_section(self, page_id: str, section_id: str) -> None:
        """Release one prepared section into its run."""
        page = self._pages.get(page_id)
        rec = page.workers.get(section_id) if page is not None else None
        if rec is not None:
            await rec.handle.send({"t": MSG_START})

    async def update_section(self, page_id: str, spec: SectionSpec) -> None:
        """Replace one section's source and restart **only** that section."""
        await self.prepare_section(page_id, spec)
        await self.launch_section(page_id, spec.id)

    async def restart_section(self, page_id: str, section_id: str) -> None:
        """Restart one section from its current source."""
        page = self._pages.get(page_id)
        if page is None or section_id not in page.specs:
            return
        await self.update_section(page_id, page.specs[section_id])

    # -- introspection -------------------------------------------------------

    def status(self, page_id: str) -> dict[str, dict[str, Any]]:
        """Current status dict per section, in the wire contract shape."""
        page = self._pages.get(page_id)
        if page is None:
            return {}
        return {sid: st.to_dict() for sid, st in page.statuses.items()}

    def fields(self, page_id: str, section_id: str) -> list[dict[str, Any]]:
        """Mount fields a compiled section owns. Not part of the status dict."""
        page = self._pages.get(page_id)
        if page is None or section_id not in page.statuses:
            return []
        return list(page.statuses[section_id].fields)

    def generation(self, page_id: str) -> int:
        """Current generation for a page (0 if never opened)."""
        return self._generations.get(page_id, 0)

    def pids(self, page_id: str) -> dict[str, int]:
        """Live worker pid per section. Debugging and tests."""
        page = self._pages.get(page_id)
        if page is None:
            return {}
        return {sid: rec.handle.pid for sid, rec in page.workers.items()}

    async def wait_for(
        self,
        page_id: str,
        states: Iterable[str],
        *,
        timeout: float = 10.0,
        sections: Iterable[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Await every section of a page reaching one of ``states``."""
        wanted = set(states)
        deadline = time.monotonic() + timeout
        while True:
            page = self._pages.get(page_id)
            current = page.statuses if page is not None else {}
            keys = set(sections) if sections is not None else set(current)
            if keys and all(sid in current and current[sid].state in wanted for sid in keys):
                return {sid: current[sid].to_dict() for sid in keys}
            if time.monotonic() > deadline:
                snapshot = {sid: st.to_dict() for sid, st in current.items()}
                raise TimeoutError(f"page {page_id!r} never settled into {wanted}: {snapshot}")
            await asyncio.sleep(0.01)

    async def _await_compiled(
        self,
        page: _Page,
        sections: Iterable[str] | None = None,
    ) -> None:
        """Wait for compilation to land, bounded. Never blocks forever."""
        keys = list(sections) if sections is not None else list(page.specs)
        if not keys:
            return
        deadline = time.monotonic() + self._compile_timeout
        while time.monotonic() < deadline:
            if self._pages.get(page.page_id) is not page:
                return
            if all(
                page.statuses[sid].compiled
                or page.statuses[sid].state in ("invalid", "failed", "stopped")
                for sid in keys
                if sid in page.statuses
            ):
                return
            await asyncio.sleep(0.002)

    # -- browser -> section --------------------------------------------------

    async def dispatch_notify(self, path: str, payload: object) -> None:
        """Route a browser notify to whichever sections subscribed to it."""
        targets = tuple(self._routes.get(path, ()))
        if not targets:
            return
        await asyncio.gather(
            *(
                rec.handle.send({"t": MSG_NOTIFY, "path": path, "payload": payload})
                for rec in targets
            ),
            return_exceptions=True,
        )

    def subscribers(self, path: str) -> list[str]:
        """Section ids currently subscribed to ``path``."""
        return [rec.section_id for rec in self._routes.get(path, ())]

    # -- internals -----------------------------------------------------------

    async def _start_section(self, page: _Page, spec: SectionSpec) -> None:
        try:
            handle = await self._pool.acquire()
        except Exception as exc:
            self._set(page, spec.id, state="failed", error=f"worker start failed: {exc}")
            return
        rec = _Worker(
            section_id=spec.id,
            page_id=page.page_id,
            generation=page.generation,
            handle=handle,
        )
        page.workers[spec.id] = rec
        rec.pump = asyncio.create_task(self._pump(page, rec))
        await handle.send(
            {
                "t": MSG_RUN,
                "section_id": spec.id,
                "prefix": spec.mount_prefix(),
                "source": spec.source,
                "store": self._store,
            },
        )

    async def _pump(self, page: _Page, rec: _Worker) -> None:
        """Drain one worker's messages until it goes quiet."""
        handle = rec.handle
        while True:
            msg = await handle.recv()
            if msg is None:
                self._on_eof(page, rec)
                return
            if self._pages.get(page.page_id) is not page:
                return  # stale generation: whatever it says no longer matters
            kind = msg.get("t")
            if kind == MSG_COMPILED:
                fields = msg.get("fields")
                self._set(page, rec.section_id, fields=fields if isinstance(fields, list) else [])
            elif kind == MSG_INVALID:
                self._set(page, rec.section_id, state="invalid", error=str(msg.get("error") or ""))
            elif kind == MSG_RUNNING:
                started = msg.get("started_at")
                self._set(
                    page,
                    rec.section_id,
                    state="running",
                    started_at=float(started) if started is not None else time.time(),
                )
            elif kind == MSG_STOPPED:
                self._set(page, rec.section_id, state="stopped")
            elif kind == MSG_FAILED:
                self._set(page, rec.section_id, state="failed", error=str(msg.get("error") or ""))
            elif kind == MSG_SEND:
                await self._forward_send(rec, msg.get("frame"))
            elif kind == MSG_READ:
                # Off the pump: a slow browser read must not stall the
                # rest of this worker's traffic.
                task = asyncio.create_task(self._forward_read(rec, msg))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            elif kind == MSG_SUBSCRIBE:
                self._route_add(rec, str(msg.get("path") or ""))
            elif kind == MSG_UNSUBSCRIBE:
                self._route_drop(rec, str(msg.get("path") or ""))

    def _on_eof(self, page: _Page, rec: _Worker) -> None:
        """The worker's pipe closed. Decide whether that was expected."""
        if self._pages.get(page.page_id) is not page:
            return
        status = page.statuses.get(rec.section_id)
        if status is None or status.state in ("invalid", "stopped", "failed"):
            return
        tail = rec.handle.stderr_tail()
        detail = f"worker exited (rc={rec.handle.returncode})"
        self._set(
            page,
            rec.section_id,
            state="failed",
            error=f"{detail}\n{tail}" if tail else detail,
        )

    async def _forward_send(self, rec: _Worker, raw: object) -> None:
        if self._host is None or not isinstance(raw, dict):
            return
        frame = Frame(
            raw.get("op"),
            ref=str(raw.get("ref") or ""),
            payload=raw.get("payload"),
            id=raw.get("id"),
        )
        with contextlib.suppress(Exception):
            await self._host.send(rec.page_id, rec.section_id, frame)

    async def _forward_read(self, rec: _Worker, msg: dict[str, Any]) -> None:
        rid = str(msg.get("id") or "")
        path = str(msg.get("path") or "")
        if self._host is None:
            await rec.handle.send({"t": MSG_READ_ERR, "id": rid, "error": "no ui host"})
            return
        try:
            payload = await self._host.aread(rec.page_id, rec.section_id, path)
        except Exception as exc:
            await rec.handle.send({"t": MSG_READ_ERR, "id": rid, "error": f"{exc}"})
            return
        await rec.handle.send({"t": MSG_READ_OK, "id": rid, "payload": payload})

    def _route_add(self, rec: _Worker, path: str) -> None:
        if not path:
            return
        rec.routes.add(path)
        self._routes.setdefault(path, set()).add(rec)

    def _route_drop(self, rec: _Worker, path: str) -> None:
        rec.routes.discard(path)
        holders = self._routes.get(path)
        if holders is None:
            return
        holders.discard(rec)
        if not holders:
            self._routes.pop(path, None)

    def _set(
        self,
        page: _Page,
        section_id: str,
        *,
        state: str | None = None,
        error: str | None = None,
        started_at: float | None = None,
        fields: list[dict[str, Any]] | None = None,
    ) -> None:
        """Mutate a section's status and publish it."""
        if self._pages.get(page.page_id) is not page:
            return
        status = page.statuses.get(section_id)
        if status is None:
            status = SectionStatus(section_id)
            page.statuses[section_id] = status
        if fields is not None:
            status.fields = fields
            status.compiled = True
        if state is not None:
            status.state = state  # type: ignore[assignment]
            if state in ("idle", "starting", "invalid"):
                status.started_at = None
        if error is not None:
            status.error = error
        if started_at is not None:
            status.started_at = started_at
        if state is not None or error is not None:
            self._publish(page, status)

    def _publish(self, page: _Page, status: SectionStatus) -> None:
        self.stream.publish(
            StatusEvent(page.page_id, page.generation, status.to_dict()),
        )

    # -- teardown ------------------------------------------------------------

    async def _teardown(self, page_id: str, *, reason: str) -> None:
        """Forget a page. Cheap and bounded: no waiting on any process."""
        page = self._pages.pop(page_id, None)
        if page is None:
            return
        for section_id in list(page.workers):
            self._detach(page, section_id)
        for status in page.statuses.values():
            if status.state in ("starting", "running", "idle"):
                status.state = reason  # type: ignore[assignment]
                status.started_at = None
                self.stream.publish(
                    StatusEvent(page.page_id, page.generation, status.to_dict()),
                )

    def _stop_section(self, page: _Page, section_id: str) -> None:
        """Detach and reap one section's worker without touching its siblings."""
        self._detach(page, section_id)

    def _detach(self, page: _Page, section_id: str) -> None:
        rec = page.workers.pop(section_id, None)
        if rec is None:
            return
        if rec.pump is not None:
            rec.pump.cancel()
            rec.pump = None
        for path in tuple(rec.routes):
            self._route_drop(rec, path)
        self._reap(rec)

    def _reap(self, rec: _Worker) -> None:
        """Run the kill ladder detached. Nothing waits on this."""
        task = asyncio.create_task(rec.handle.stop(self._timeouts))
        self._reaping.add(task)
        task.add_done_callback(self._reaping.discard)
