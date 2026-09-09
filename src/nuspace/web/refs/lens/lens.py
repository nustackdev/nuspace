"""LensRef -- Miller-columns browser over any Nu Shape.

Product-side + protocol notes: ``go/projects/nustackdev/nuspace/lens.md``.

Two moving parts:

- ``LensRef``: a nu.ui Ref. Pure wire handle -- payload is stamped once
  in ``__init__`` (root Shape class, max_rows cap) and never mutated
  afterward. Root is Python-only, not shipped over the wire; max_rows
  rides in mount props so the TS slice can seed. ``set_path`` is the
  one host-driving verb; ``path_changed()`` returns ``Changed(self)``
  so drivers can subscribe to browser notifies. The cursor itself
  lives in the browser slice (``value.path``); server holds no runtime
  state between notifies.

- ``LensDriver``: per-connection driver. On boot it emits the root
  column with an empty path. Then loops on browser notifies: each
  carries a browser-computed full path, driver recomputes columns for
  that path and writes ``{path, columns}`` back. No ref-side storage.
  Adding new observers (URL syncer, logger, ...) is a sibling
  ReactForever -- no fork of the driver.

Server-owned wire payload (msgpack-native, per TableRef pattern):

    {"path": [...segments...], "columns": [...]}

Each column:

    {"kind": "shape"|"mapping"|"sequence"|"leaf",
     "entries": [{"key": str, "kind": str, "preview": str, "navigable": bool,
                  "vtype": str, "text": str, "clipped": bool}],
     "total": int}

``kind`` is the *structural* kind (which column shape a row leads to).
``vtype`` is the *value* type of what the row holds -- "str", "int",
"float", "bool", "bytes", "none", "empty", "invalid", "ref" (a shape
slot, not a value yet), or "" (nothing to type). The browser renders a
value by ``vtype``: an int, a string, a sentinel and an empty slot have
to be distinguishable at a glance, and reparsing ``preview`` (a repr)
client-side to recover that is guesswork. ``text`` / ``clipped`` ride
along on leaf rows only: ``preview`` is a 120-char repr fit for a table
cell, and a leaf column renders the value in full, so it needs the
untruncated text (capped at ``MAX_LEAF_TEXT``) rather than the cell repr.

Browser notify shape (client -> server):

    {"path": [...full new path...]}

v1 skips delta shipping -- every notify triggers a full replace.
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
from nu.lang import Command, Control
from nu.lang.sentinels import EMPTY, INVALID
from nu.ui.core import Ref, Session
from nu.ui.core.protocol import Frame


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape
    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang.runtime import Runtime


__all__ = ["LensDriver", "LensRef"]


DEFAULT_MAX_ROWS = 200

# How much of a leaf value the leaf column gets in full. A section's
# source text is the realistic worst case and lands well under this; past
# it the browser shows a "clipped" note instead of pretending.
MAX_LEAF_TEXT = 4000


# -- Ref ---------------------------------------------------------------------


class LensRef(Ref):
    """A browsable window onto a Nu Shape.

    Configure once with a root Shape class. The server owns the path and
    columns; the browser renders and emits notify frames with the full
    new path on user navigation. External Nu code drives the cursor by
    invoking ``set_path`` on this ref.
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
        # No runtime state on the ref. Cursor lives in the browser
        # slice; server recomputes columns from the path each notify
        # carries. Mutating _payload after construction would bleed
        # across Nu tree rewrites that reuse the payload reference.

    @classmethod
    def slot(  # noqa: D102
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
        return _LensSetPath(self, tuple(str(s) for s in path))

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
    """Build the substrate ref at ``path`` from the root Shape class."""
    if not path:
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
                # A slot is a declaration, not a value: nothing has been
                # read yet, so the row types as "ref" and the browser
                # renders the ref class name as a type tag, not a value.
                "vtype": "ref",
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
        {"key": str(k), "kind": "shape", "preview": "", "navigable": True, "vtype": ""}
        for k in keys
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
        {
            "key": str(i),
            "kind": "leaf",
            "preview": _preview(v),
            "navigable": True,
            "vtype": _vtype(v),
        }
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
    vtype = ""
    try:
        value, _ = await nu.arun(term, ctx)  # type: ignore[arg-type]
        vtype = _vtype(value)
    except Exception as exc:
        value = f"<error: {exc!r}>"
        vtype = "error"
    text, clipped = _full_text(value)
    entries = [
        {
            "key": "value",
            "kind": "leaf",
            "preview": _preview(value),
            "navigable": False,
            "vtype": vtype,
            "text": text,
            "clipped": clipped,
        },
    ]
    return {"kind": "leaf", "entries": entries, "total": 1}


def _preview(value: object) -> str:
    """Compact repr for a leaf value, trimmed for the column cell."""
    s = repr(value)
    return s if len(s) <= 120 else s[:117] + "..."


def _vtype(value: object) -> str:
    """Value-type token for a leaf, so the browser can render by type.

    Sentinels come first: ``EMPTY`` is a real, common state on this
    surface (a declared slot nothing has written yet) and reads nothing
    like a missing key or a ``None``, so it gets its own token rather
    than falling through to ``other``.
    """
    if value is EMPTY:
        return "empty"
    if value is INVALID:
        return "invalid"
    if value is None:
        return "none"
    if isinstance(value, bool):  # before int: bool is an int subclass
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, (bytes, bytearray)):
        return "bytes"
    if isinstance(value, (list, tuple)):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return "other"


def _full_text(value: object) -> tuple[str, bool]:
    """Untruncated-ish text for the leaf column, plus a clipped flag."""
    if isinstance(value, (bytes, bytearray)):
        s = value.decode("utf-8", "replace")
    elif isinstance(value, str):
        s = value
    else:
        s = repr(value)
    if len(s) <= MAX_LEAF_TEXT:
        return s, False
    return s[:MAX_LEAF_TEXT], True


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


async def _emit(
    session: Session,
    wire_path: str,
    root: type[Shape],
    path: tuple[str, ...],
    max_rows: int,
    ctx: object,
) -> None:
    """Recompute columns and ship one write frame."""
    columns = await _all_columns(root, path, max_rows, ctx)
    payload = {"path": list(path), "columns": columns}
    await session.send(Frame("write", ref=wire_path, payload=payload))


# -- Command: host-side set_path --------------------------------------------


class _LensSetPath(Command):
    """Set the cursor to a specific path and re-emit."""

    _mutates = Declared(value=frozenset({0}), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")

    def __init__(self, ref: LensRef, path: tuple[str, ...]) -> None:
        super().__init__(ref)
        self._payload["lens_target_path"] = tuple(str(s) for s in path)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("LensRef is async-only; use nu.arun")

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref: LensRef = self._children[0]
        target: tuple[str, ...] = self._payload["lens_target_path"]
        root: type[Shape] | None = ref._payload.get("lens_root")
        max_rows: int = ref._payload.get("lens_max_rows", DEFAULT_MAX_ROWS)
        if root is None:
            raise RuntimeError("LensRef.slot(root=...) requires a Shape class")

        async def athunk(rt: Runtime) -> None:
            session = rt.ctx.get(Session)
            ref_nid = rt.program.children[nid][0]
            wire_path = await ref._aresolve_address(rt, ref_nid)
            await _emit(session, wire_path, root, target, max_rows, rt.ctx)

        return athunk


# -- Driver ------------------------------------------------------------------


class LensDriver(Control):
    """Per-connection driver: mount, subscribe, react.

    Ships the root column (empty path) on mount so the browser paints
    immediately. Then loops on notifies: each carries a browser-computed
    full path; the driver recomputes columns for that path and writes
    back. Path is a loop-local variable, never stored on the ref -- the
    browser slice owns the cursor.

    Runs forever inside the app tree, alongside any other reactive body.
    Adding another observer on ``ref.path_changed()`` is a sibling
    ReactForever -- no fork here.
    """

    _mutates = Declared(value=frozenset(), name="mutates")
    _requires_async = Declared(value=True, name="requires_async")
    _param_slots = Declared(value=frozenset({0}), name="param_slots")

    def __init__(self, ref: LensRef) -> None:
        super().__init__(ref)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> None:
            raise RuntimeError("LensDriver is async-only; use nu.arun")

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

            # initial paint: root column, empty path. Reload starts here
            # every time -- persistence across reload is an explicit v2
            # choice (backing the cursor with nu.mem/nu.kv), not an
            # accidental side effect of server-held state.
            await _emit(session, wire_path, root, (), max_rows, rt.ctx)

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
                    raw_path = payload.get("path")
                    if not isinstance(raw_path, (list, tuple)):
                        continue
                    new_path = tuple(str(s) for s in raw_path)
                    # Loop-local; no ref-side storage.
                    await _emit(session, wire_path, root, new_path, max_rows, rt.ctx)
            finally:
                sub.unbind(on_notify)
                sub.close()

        return athunk
