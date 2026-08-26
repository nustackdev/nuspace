"""LensRef -- Miller-columns browser over any Nu Shape.

Product-side + protocol notes: ``go/projects/nustackdev/nuspace/lens.md``.

Two moving parts:

- ``LensRef``: a nu.ui Ref. Slot factory stamps the ``root`` Shape class and
  ``max_rows`` cap on the ref payload (root is Python-only, not shipped over
  the wire; max_rows rides in mount props so the TS slice can seed).
  Interactions ``set_path`` / ``push_segment`` / ``pop_segment`` build the
  outgoing wire payload directly and ship it via the ``NudleSession``.
  ``path_changed`` returns ``Changed(self)`` so app code can subscribe.

- ``LensRun``: a Control that owns the per-connection cursor state, subscribes
  to notifies for the ref, and drives column recomputation on every event.
  Composed into the app tree; keeps orchestration outside the ref so the ref
  itself stays a plain surface anyone can drive.

Server-owned wire payload (msgpack-native, per TableRef pattern):

    {"action": "replace", "path": [...segments...], "columns": [...]}

Each column:

    {"kind": "shape"|"mapping"|"sequence"|"leaf",
     "entries": [{"key": str, "kind": str, "preview": str, "navigable": bool}],
     "total": int}

v1 skips delta shipping -- every navigation is a full replace. Delta actions
(``append`` / ``pop``) land after v1 works end-to-end.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from typing_extensions import Self

import nu
from nu.domains.shape.refs.item import ItemRef
from nu.domains.shape.refs.mapping import MappingRef
from nu.domains.shape.refs.sequence import SequenceRef
from nu.domains.shape.refs.shape import ShapeRef
from nu.domains.shape.refs.shapes_mapping import ShapesMappingRef
from nu.engine.structure import Declared
from nu.lang import Control
from nu.ui.core import Ref, Session
from nu.ui.core.protocol import Frame


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang.runtime import Runtime


__all__ = ["LensRef", "LensRun"]


DEFAULT_MAX_ROWS = 200


# -- Ref ---------------------------------------------------------------------


class LensRef(Ref):
    """A browsable window onto a Nu Shape.

    Configure once with a root Shape class. The server drives the columns
    payload; the browser only renders and emits notify frames for user
    navigation (click a row / press an arrow). External Nu code can drive
    the cursor by invoking ``set_path`` / ``push_segment`` / ``pop_segment``
    on this ref.
    """

    # Bind the browser factory by name -- LensRef lives outside nu.ui.refs
    # so the MRO walk in _wire_type would miss it otherwise.
    _wire_type_override = "LensRef"

    def __init__(
        self,
        address: object,
        *,
        parent_ref: Ref | None = None,
        owner_shape: type[Shape] | None = None,
        root_shape: type[Shape] | None = None,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> None:
        super().__init__(address, parent_ref=parent_ref, owner_shape=owner_shape)
        self._payload["lens_root"] = root_shape
        self._payload["lens_max_rows"] = int(max_rows)

    @classmethod
    def slot(
        cls,
        *,
        root: type[Shape],
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> Self:
        # ``root`` rides in kwargs (Python only). ``max_rows`` rides in props
        # too so the TS slice can seed and cap client-side buffers.
        return nu.Slot(  # type: ignore[return-value]
            cls,
            props={"max_rows": int(max_rows)},
            root_shape=root,
            max_rows=int(max_rows),
        )

    # -- Interactions --------------------------------------------------------

    def set_path(self, path: tuple[str, ...]) -> nu.Nu:
        """Replace the cursor with ``path`` and re-emit columns."""
        return _LensDrive(self, ("replace", tuple(str(s) for s in path), None))

    def push_segment(self, segment: str) -> nu.Nu:
        """Descend one level by appending ``segment`` to the current path."""
        return _LensDrive(self, ("push", None, str(segment)))

    def pop_segment(self) -> nu.Nu:
        """Ascend one level -- drop the last path segment."""
        return _LensDrive(self, ("pop", None, None))

    def path_changed(self) -> nu.Nu:
        """Subscribe to browser NOTIFY frames on this ref."""
        return nu.ui.Changed(self)


# -- Wire helpers ------------------------------------------------------------


def _slot_kind(ref_cls: type) -> str:
    """Coarse label used for kind dots + previews."""
    if issubclass(ref_cls, (ShapesMappingRef, MappingRef)):
        return "mapping"
    if issubclass(ref_cls, SequenceRef):
        return "sequence"
    if issubclass(ref_cls, ShapeRef):
        return "shape"
    if issubclass(ref_cls, ItemRef):
        return "leaf"
    return "unknown"


def _descend(root: type[Shape], path: tuple[str, ...]) -> StructuredRef:
    """Build the substrate ref at ``path`` from the root Shape class.

    Uses the class-level SlotDescriptor for the first hop, then bracket
    access on the resulting refs (works for ShapeRef, MappingRef, ...).
    """
    if not path:
        # A "root column" doesn't have a substrate ref; the caller handles
        # this case by walking the root class's slots directly.
        raise ValueError("_descend needs at least one segment")
    ref = getattr(root, path[0])
    for seg in path[1:]:
        ref = ref[seg]
    return ref


async def _shape_column(shape_cls: type[Shape]) -> dict[str, Any]:
    """Column payload for a Shape: its slot list, no kv touch."""
    entries: list[dict[str, Any]] = []
    for name, slot in shape_cls._slots.items():
        kind = _slot_kind(slot.ref_cls)
        entries.append(
            {
                "key": name,
                "kind": kind,
                "preview": slot.ref_cls.__name__,
                "navigable": True,
            },
        )
    return {"kind": "shape", "entries": entries, "total": len(entries)}


async def _mapping_column(
    ref: StructuredRef,
    ctx: object,
    max_rows: int,
    *,
    root: type[Shape],
) -> dict[str, Any]:
    """Column payload for a mapping ref: keys, capped at ``max_rows``."""
    from nu.kv.tree import auto_flow_atomic

    keys_term = auto_flow_atomic(nu.Collect(nu.Iter(ref)), scope=root)
    raw, _ = await nu.arun(keys_term, ctx)  # type: ignore[arg-type]
    keys = list(raw or [])
    total = len(keys)
    keys = keys[:max_rows]
    entries = [
        {"key": str(k), "kind": "shape", "preview": "", "navigable": True} for k in keys
    ]
    return {"kind": "mapping", "entries": entries, "total": total}


async def _sequence_column(
    ref: StructuredRef,
    ctx: object,
    max_rows: int,
    *,
    root: type[Shape],
) -> dict[str, Any]:
    """Column payload for a sequence ref: indexed rows, capped."""
    from nu.kv.tree import auto_flow_atomic

    values_term = auto_flow_atomic(nu.Collect(nu.Iter(ref)), scope=root)
    raw, _ = await nu.arun(values_term, ctx)  # type: ignore[arg-type]
    values = list(raw or [])
    total = len(values)
    values = values[:max_rows]
    entries = [
        {"key": str(i), "kind": "leaf", "preview": _preview(v), "navigable": True}
        for i, v in enumerate(values)
    ]
    return {"kind": "sequence", "entries": entries, "total": total}


async def _leaf_column(
    ref: StructuredRef,
    ctx: object,
    *,
    root: type[Shape],
) -> dict[str, Any]:
    """Column payload for a leaf ref: its current value."""
    from nu.kv.tree import auto_flow_atomic

    term = auto_flow_atomic(ref, scope=root)
    try:
        value, _ = await nu.arun(term, ctx)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 -- surface any error as an entry
        value = f"<error: {exc!r}>"
    entries = [
        {"key": "value", "kind": "leaf", "preview": _preview(value), "navigable": False},
    ]
    return {"kind": "leaf", "entries": entries, "total": 1}


def _preview(value: object) -> str:
    """Compact repr for a leaf value, trimmed for the column cell."""
    s = repr(value)
    return s if len(s) <= 120 else s[:117] + "..."


async def _column_for(
    root: type[Shape],
    path: tuple[str, ...],
    max_rows: int,
    ctx: object,
) -> dict[str, Any]:
    """Protocol dispatch: build the column payload for the last segment of ``path``."""
    if not path:
        return await _shape_column(root)
    ref = _descend(root, path)
    if isinstance(ref, ShapeRef):
        shape_cls = ref._payload["shape_type"]
        return await _shape_column(shape_cls)
    if isinstance(ref, (ShapesMappingRef, MappingRef)):
        return await _mapping_column(ref, ctx, max_rows, root=root)
    if isinstance(ref, SequenceRef):
        return await _sequence_column(ref, ctx, max_rows, root=root)
    if isinstance(ref, ItemRef):
        return await _leaf_column(ref, ctx, root=root)
    return await _leaf_column(ref, ctx, root=root)


async def _all_columns(
    root: type[Shape],
    path: tuple[str, ...],
    max_rows: int,
    ctx: object,
) -> list[dict[str, Any]]:
    """Full cascade: one column per prefix of ``path`` (including root)."""
    out: list[dict[str, Any]] = [await _column_for(root, (), max_rows, ctx)]
    for i in range(1, len(path) + 1):
        out.append(await _column_for(root, path[:i], max_rows, ctx))
    return out


# -- Command: ship a payload -------------------------------------------------


class _LensDrive(nu.lang.Command):
    """Ship one write frame for a LensRef: apply ``op`` to current path, re-emit.

    Cursor state lives in ``rt.ctx.attrs`` keyed by wire path, so a single
    connection sees a consistent cursor across ``set_path`` / ``push`` / ``pop``
    invocations. External Nu code driving the cursor and browser-side notify
    handling share this same state.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(
        self,
        ref: LensRef,
        op: tuple[str, tuple[str, ...] | None, str | None],
    ) -> None:
        super().__init__(ref)
        self._payload["lens_op"] = op

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("LensRef is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: LensRef = self._children[0]
        op = self._payload["lens_op"]
        root: type[Shape] | None = ref._payload.get("lens_root")
        max_rows: int = ref._payload.get("lens_max_rows", DEFAULT_MAX_ROWS)
        if root is None:
            raise RuntimeError("LensRef.slot(root=...) requires a Shape class")

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            state_key = f"_lens_path::{wire_path}"
            current = list(rt.ctx.attrs.get(state_key, ()))
            action, new_path, segment = op
            if action == "replace":
                current = list(new_path or ())
            elif action == "push" and segment is not None:
                current.append(segment)
            elif action == "pop" and current:
                current.pop()
            rt.ctx.attrs[state_key] = tuple(current)
            columns = await _all_columns(root, tuple(current), max_rows, rt.ctx)
            payload = {"action": "replace", "path": list(current), "columns": columns}
            await session.send(Frame("write", ref=wire_path, payload=payload))

        return athunk


# -- Driver ------------------------------------------------------------------


class LensRun(Control):
    """Per-connection driver: mount, subscribe, react.

    On mount ships the initial (empty path) column so the browser paints
    something. Then subscribes to notify frames on the ref and applies the
    action payload to the cursor, re-emitting columns each time.

    Runs forever inside the app tree, alongside any other reactive body.
    """

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: LensRef) -> None:
        super().__init__(ref)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("LensRun is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: LensRef = self._children[0]
        root: type[Shape] | None = ref._payload.get("lens_root")
        max_rows: int = ref._payload.get("lens_max_rows", DEFAULT_MAX_ROWS)
        if root is None:
            raise RuntimeError("LensRef.slot(root=...) requires a Shape class")

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            state_key = f"_lens_path::{wire_path}"
            if state_key not in rt.ctx.attrs:
                rt.ctx.attrs[state_key] = ()

            async def emit() -> None:
                path = tuple(rt.ctx.attrs[state_key])
                columns = await _all_columns(root, path, max_rows, rt.ctx)
                payload = {"action": "replace", "path": list(path), "columns": columns}
                await session.send(Frame("write", ref=wire_path, payload=payload))

            await emit()

            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[object] = asyncio.Queue()

            def on_notify(payload: object) -> None:
                loop.call_soon_threadsafe(queue.put_nowait, payload)

            sub = session.subscribe(wire_path)
            sub.bind(on_notify)
            try:
                while True:
                    payload = await queue.get()
                    if not isinstance(payload, dict):
                        continue
                    action = payload.get("action")
                    current = list(rt.ctx.attrs[state_key])
                    if action == "push":
                        seg = payload.get("segment")
                        if seg is None:
                            continue
                        current.append(str(seg))
                    elif action == "pop":
                        if current:
                            current.pop()
                    elif action == "replace":
                        current = [str(s) for s in payload.get("path", [])]
                    else:
                        continue
                    rt.ctx.attrs[state_key] = tuple(current)
                    await emit()
            finally:
                sub.unbind(on_notify)
                sub.close()

        return athunk
