"""Per-section supervision seam + the in-process stub that fills it for v1.

task-139 splits into an out-of-process executor and this editor. The
executor is being built in parallel, so this module owns the *seam* and
ships a local implementation behind it so the editor is exercisable end
to end today.

The status contract is fixed and shared with the executor. Do not
redesign it here:

    {"section_id": str,
     "state": "invalid"|"idle"|"starting"|"running"|"stopped"|"failed",
     "error": str|None,
     "started_at": float|None}

``invalid`` = never constructed a tree; ``error`` carries the
``nu.prog`` :class:`~nu.prog.Diagnostic`, rendered as its message plus
the line in the section's own source. ``failed`` = it constructed, ran,
and died.

Construction itself is nu's. ``nuspace.exec.compile.construct_section``
is ``nu.prog``'s in-process brace with ``path`` bound into the entry
point's scope; a section is a module with an ``out`` function, not an
expression.

``SectionSupervisor`` is the interface the driver talks to. Swapping in
the real executor means writing a second implementation of these five
methods; nothing in ``pages.py`` or the browser knows the difference.

``LocalSupervisor`` is the v1 stub. One asyncio task per section, not one
folded task per page. That is deliberate: it is the weakest thing that
still gives per-section restart, per-section failure isolation, and
per-section status, which is exactly the surface the editor renders. What
it does *not* give is the kill guarantee -- an asyncio task wedged in a C
call can only be marked and abandoned. That is the whole reason the real
executor is out of process, and it is the one behaviour this stub cannot
fake.

Two-phase start, because ordering matters. ``plan()`` compiles and
returns each section's mount fields; the driver ships them to the browser
so the slices exist; only then does ``launch()`` start the tasks. Frames
are ordered on the ws, so that is enough to guarantee a section never
writes to a slice the browser has not registered.
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import nu
from nu.kv.tree import auto_flow_atomic
from nu.prog import Diagnostic
from nuspace.exec.compile import construct_section, enumerate_ui_refs


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape


__all__ = [
    "STATES",
    "LocalSupervisor",
    "SectionSpec",
    "SectionStatus",
    "SectionSupervisor",
]


STATES = ("invalid", "idle", "starting", "running", "stopped", "failed")

# Bounded teardown. The local stub can only wait -- there is no signal to
# escalate to in-process. The executor replaces this with TERM then KILL.
STOP_GRACE_S = 2.0

# Sentinel: "leave started_at alone" (None is a meaningful value).
_KEEP: Any = object()


@dataclass
class SectionStatus:
    """One section's observable state. Mirrors the wire contract exactly."""

    section_id: str
    state: str = "idle"
    error: str | None = None
    started_at: float | None = None

    def to_wire(self) -> dict[str, Any]:
        """The wire form, exactly as the browser block chrome consumes it."""
        return {
            "section_id": self.section_id,
            "state": self.state,
            "error": self.error,
            "started_at": self.started_at,
        }


@dataclass
class SectionSpec:
    """What the driver asks the supervisor to run: id + source, nothing else."""

    section_id: str
    source: str

    @property
    def prefix(self) -> str:
        """The mount prefix. Path is the mounting mechanism."""
        return f"sections.{self.section_id}"


@dataclass
class _Generation:
    """One running instance of one section."""

    spec: SectionSpec
    status: SectionStatus
    fields: list[dict[str, Any]] = field(default_factory=list)
    term: Any = None
    task: asyncio.Task | None = None


class SectionSupervisor(ABC):
    """Five methods. The executor implements the same five."""

    @abstractmethod
    def plan(self, specs: list[SectionSpec]) -> dict[str, _Generation]:
        """Reconcile to ``specs``: compile new/changed, retire removed.

        Returns the current generation map. Sections whose source is
        unchanged and already running are left completely alone -- that
        is what "edit one block, only that block restarts" means.
        Nothing is started here; call ``launch()`` after shipping.
        """

    @abstractmethod
    async def launch(self) -> None:
        """Start every section that ``plan`` left pending."""

    @abstractmethod
    async def restart(self, section_id: str) -> None:
        """Stop then recompile then relaunch one section."""

    @abstractmethod
    async def stop_all(self) -> None:
        """Bounded teardown of every section. Idempotent."""

    @abstractmethod
    def statuses(self) -> list[dict[str, Any]]:
        """Current status of every known section, wire-shaped."""

    def on_change(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """Register a status-change observer. Called on the event loop."""
        raise NotImplementedError


class LocalSupervisor(SectionSupervisor):
    """In-process stub: one asyncio task per section.

    ``ctx`` is the Nu runtime context the driver runs under; ``scope`` is
    the Shape class every section's term is flowed against.
    """

    def __init__(self, ctx: object, scope: type[Shape]) -> None:
        self._ctx = ctx
        self._scope = scope
        self._gens: dict[str, _Generation] = {}
        self._pending: list[str] = []
        self._observers: list[Callable[[dict[str, Any]], None]] = []

    # -- observation ---------------------------------------------------------

    def on_change(self, cb: Callable[[dict[str, Any]], None]) -> None:
        """Register a status-change observer. Called on the event loop."""
        self._observers.append(cb)

    def _emit(self, gen: _Generation) -> None:
        wire = gen.status.to_wire()
        for cb in list(self._observers):
            try:
                cb(wire)
            except Exception:  # noqa: S110 -- an observer must not break supervision
                pass

    def _set(
        self,
        gen: _Generation,
        state: str,
        *,
        error: str | None = None,
        started_at: float | None = _KEEP,  # type: ignore[assignment]
    ) -> None:
        gen.status.state = state
        gen.status.error = error
        if started_at is not _KEEP:
            # `started_at` survives stopped/failed on purpose -- the block
            # chrome wants to say how long it ran before it died.
            gen.status.started_at = started_at
        self._emit(gen)

    # -- reconcile -----------------------------------------------------------

    def plan(self, specs: list[SectionSpec]) -> dict[str, _Generation]:
        """Reconcile to ``specs``. Unchanged, still-running sections are untouched."""
        wanted = {s.section_id: s for s in specs}

        # Retire sections that vanished. Cancel now, reap in launch().
        for sid in list(self._gens):
            if sid not in wanted:
                self._cancel(self._gens.pop(sid))

        self._pending = []
        for sid, spec in wanted.items():
            existing = self._gens.get(sid)
            if (
                existing is not None
                and existing.spec.source == spec.source
                and existing.status.state in ("running", "starting")
            ):
                # Untouched and alive. Leave it exactly as it is.
                continue
            if existing is not None:
                self._cancel(existing)
            self._gens[sid] = self._compile(spec)
            if self._gens[sid].status.state != "invalid":
                self._pending.append(sid)
        return dict(self._gens)

    def _compile(self, spec: SectionSpec) -> _Generation:
        gen = _Generation(spec=spec, status=SectionStatus(spec.section_id))
        if not spec.source.strip():
            gen.status.state = "idle"
            return gen
        term = construct_section(spec.source, spec.prefix)
        if isinstance(term, Diagnostic):
            # No tree ever existed, so it never ran: `invalid`, not
            # `failed`. `str(Diagnostic)` carries the message and, when
            # there is one, the line in the section's own source.
            gen.status.state = "invalid"
            gen.status.error = str(term)
            return gen
        gen.term = term
        gen.fields = enumerate_ui_refs(term, spec.prefix)
        gen.status.state = "idle"
        return gen

    # -- lifecycle -----------------------------------------------------------

    async def launch(self) -> None:
        """Start every section ``plan`` left pending."""
        pending, self._pending = self._pending, []
        for sid in pending:
            gen = self._gens.get(sid)
            if gen is None or gen.term is None:
                continue
            self._start(gen)

    def _start(self, gen: _Generation) -> None:
        self._set(gen, "starting", started_at=time.time())
        body = auto_flow_atomic(gen.term, scope=self._scope)

        async def run() -> None:
            try:
                self._set(gen, "running")
                await nu.arun(body, self._ctx)  # type: ignore[arg-type]
            except asyncio.CancelledError:
                self._set(gen, "stopped")
                raise
            except Exception as exc:
                self._set(gen, "failed", error=f"{type(exc).__name__}: {exc}")
                return
            # A section body that returns has finished cleanly. Most carry a
            # ReactForever and never get here.
            self._set(gen, "stopped")

        gen.task = asyncio.create_task(run())

    def _cancel(self, gen: _Generation) -> None:
        task = gen.task
        gen.task = None
        if task is not None and not task.done():
            task.cancel()

    async def restart(self, section_id: str) -> None:
        """Stop, recompile, relaunch one section. Neighbours are not touched."""
        gen = self._gens.get(section_id)
        if gen is None:
            return
        spec = gen.spec
        await self._stop(gen)
        fresh = self._compile(spec)
        self._gens[section_id] = fresh
        if fresh.status.state == "invalid":
            self._emit(fresh)
            return
        if fresh.term is not None:
            self._start(fresh)
        else:
            self._emit(fresh)

    async def _stop(self, gen: _Generation) -> None:
        task = gen.task
        gen.task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=STOP_GRACE_S)
        except (TimeoutError, asyncio.CancelledError, Exception):  # noqa: S110
            # In-process there is nothing to escalate to. The task is
            # abandoned and its status is left where it landed. This is
            # precisely the hole the out-of-process executor closes.
            pass

    async def stop_all(self) -> None:
        """Bounded teardown of every section. Idempotent."""
        gens = list(self._gens.values())
        self._gens = {}
        self._pending = []
        for gen in gens:
            self._cancel(gen)
        for gen in gens:
            await self._stop(gen)

    # -- readout -------------------------------------------------------------

    def statuses(self) -> list[dict[str, Any]]:
        """Current status of every known section, wire-shaped."""
        return [g.status.to_wire() for g in self._gens.values()]

    def fields(self, section_id: str) -> list[dict[str, Any]]:
        """Mount fields the section owns, from its last successful compile."""
        gen = self._gens.get(section_id)
        return list(gen.fields) if gen else []

    def status(self, section_id: str) -> dict[str, Any]:
        """One section's status, wire-shaped. Unknown ids read as ``idle``."""
        gen = self._gens.get(section_id)
        if gen is None:
            return SectionStatus(section_id).to_wire()
        return gen.status.to_wire()
