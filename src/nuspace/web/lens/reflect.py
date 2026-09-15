"""Turning a Shape and a path into columns, without an opaque callable anywhere.

The lens is the one nuspace surface whose answer is not a kv query over a
known address: the address itself arrives from the browser. ``Space.apps`` is
structure the compiler folds into a wire address, so ``getattr(root, seg)``
for a ``seg`` that only exists at runtime is not something a Nu term can say.

The split that gets around it without smuggling python into an atom:

- :func:`column_terms` is an **ordinary ``-> Nu`` builder**. Given a root
  Shape class and a concrete path it walks the Shape hierarchy in python and
  returns a Nu term that reads whatever kv has to be read. It is a function,
  not an atom, exactly per nu's authoring rule -- it composes, it introduces
  no thunk.
- :data:`LensColumns` is that builder behind :func:`nu.host`, so the path can
  be a runtime value. The callable is fixed at class definition time, which
  is the sanctioned escape: the callable is code, not data. Its children are
  the root (a class, an address), the path and the cap.
- :func:`columns` hands ``LensColumns`` to :class:`nu.Eval`, which compiles
  the produced term against the running program and drives it in the same
  ctx. The kv reads stay inside nu's evaluator; no nested ``nu.arun``, no
  python reading the store.

:data:`LensCell` and :data:`LensFailed` are the other two host atoms, and the
small ones: a value's row and a caught error's row are pure functions of one
value, and spelling ``repr``-with-a-cap as a Nu tree would buy nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nustd.kv
from nu.domains.shape.refs.item import ItemRef
from nu.domains.shape.refs.mapping import MappingRef
from nu.domains.shape.refs.sequence import SequenceRef
from nu.domains.shape.refs.shape import ShapeRef
from nu.domains.shape.refs.shapes_mapping import ShapesMappingRef
from nu.lang.attributes import Cardinality
from nu.lang.sentinels import EMPTY, INVALID


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nu.domains.shape.refs.base import StructuredRef


__all__ = [
    "DEFAULT_MAX_ROWS",
    "LensCell",
    "LensColumns",
    "LensFailed",
    "column_terms",
    "columns",
]


#: How many rows one column ships. Hard cap, no pagination: the browser seeds
#: from the same number in its mount props, and a column says ``n/total`` when
#: it has been clipped.
DEFAULT_MAX_ROWS = 200

#: What a row's ``preview`` is trimmed to, and what the leaf reader pane gets.
PREVIEW = 120
TEXT = 4000


def _loop(depth: int) -> tuple[str, nu.Nu]:
    """The name one column's ``Map`` binds its element under, and a ref for it.

    Per column rather than one shared name: columns are siblings under one
    ``List``, and two of them binding one key would read each other's element
    the moment either awaited.
    """
    name = f"_lens_item{depth}"
    return name, nu.AnyAttrRef(name)


# --- one row ----------------------------------------------------------------


def _vtype(value: object) -> str:
    """The wire word for a value's type. Sentinels get their own words."""
    if value is EMPTY:
        return "empty"
    if value is INVALID:
        return "invalid"
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float, str, bytes, list, tuple, dict)):
        return {"tuple": "list"}.get(type(value).__name__, type(value).__name__)
    return type(value).__name__


def _text(value: object) -> str:
    """A value as the browser should read it. Strings unquoted, the rest repr'd."""
    if value is EMPTY or value is INVALID or value is None:
        return ""
    return value if isinstance(value, str) else repr(value)


def _cell(key: str, value: object, kind: str, navigable: bool, full: bool) -> dict[str, Any]:
    """One wire row, plus the untruncated ``text`` when ``full``.

    A row is ``{key, kind, preview, navigable, vtype}``. ``full`` is the leaf
    column's single row, which gets a reader pane; every other row is a line
    in a list and carries the trimmed preview only.
    """
    body = _text(value)
    row: dict[str, Any] = {
        "key": key,
        "kind": kind,
        "preview": body[:PREVIEW],
        "navigable": navigable,
        "vtype": _vtype(value),
    }
    if full:
        row["text"] = body[:TEXT]
        row["clipped"] = len(body) > TEXT
    return row


#: One row, from one value. Sentinels are the answer here rather than a reason
#: to short-circuit: an unwritten slot renders as ``empty``, visibly.
LensCell = nu.host(_cell, name="LensCell", propagate_sentinels=False)


# --- the walk ---------------------------------------------------------------


def _kind_of(ref_cls: type) -> str:
    """The column a ref of this class opens. The browser's ``kind`` vocabulary."""
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
    """The ref at ``path``, built segment by segment from the root class.

    The first segment is a slot on the root class; after that it is uniformly
    ``[]``, since a ShapeRef indexes its slots by name and a mapping ref
    indexes its keys. Raises on a segment that names nothing, which the
    caller turns into one error column.
    """
    ref: Any = _slot(root, path[0])
    for seg in path[1:]:
        if isinstance(ref, ItemRef):
            # A leaf has nothing under it, and indexing one builds a term that
            # fails much later, inside the codec, with a much worse message.
            msg = f"{seg!r}: a value has nothing under it"
            raise KeyError(msg)
        ref = _slot(ref, seg) if isinstance(ref, ShapeRef) else ref[seg]
    return ref


def _slot(owner: Any, name: str) -> Any:  # noqa: ANN401 -- a Shape class or a ShapeRef
    """One named slot off a Shape class or a ShapeRef, or a ``KeyError``."""
    shape_cls = owner._payload["shape_type"] if isinstance(owner, ShapeRef) else owner
    if name not in shape_cls._slots:
        msg = f"{name!r}: no such slot on {shape_cls.__name__}"
        raise KeyError(msg)
    return getattr(owner, name)


def _column(kind: str, entries: nu.Nu, total: nu.Nu) -> nu.Nu:
    """One column, in the shape the browser's slice reads."""
    return nu.Dict.of(kind=nu.Str(kind), entries=entries, total=total)


def _shape_term(shape_cls: type[Shape], at: Any) -> nu.Nu:  # noqa: ANN401
    """A Shape's slots, one row each. Leaf slots carry their value.

    The slot list is schema, so it is settled here in python and there is
    nothing to cap; only the leaf slots read anything, and each of those is a
    plain ref read the compiler sees.
    """
    entries: list[nu.Nu] = []
    for name, slot in shape_cls._slots.items():
        kind = _kind_of(slot.ref_cls)
        if kind == "leaf":
            entries.append(LensCell(name, getattr(at, name), kind, True, False))
        else:
            entries.append(
                nu.Literal(
                    {"key": name, "kind": kind, "preview": "", "navigable": True, "vtype": ""}
                )
            )
    return _column("shape", nu.List.of(*entries), nu.Int(len(entries)))


def _mapping_term(ref: StructuredRef, max_rows: int, depth: int) -> nu.Nu:
    """A mapping's keys, capped, with the total beside them.

    Bound once with ``Let``: the cap and the total are two reads of one key
    list, and iterating a container twice to answer one column would be a
    second pass over the store for nothing.
    """
    held = f"_lens_keys{depth}"
    item, elem = _loop(depth)
    keys = nu.ListAttrRef(held)
    if isinstance(ref, ShapesMappingRef):
        # The values are Shapes. A key is a door, not a value, so it says so
        # and reads nothing.
        row: nu.Nu = nu.Dict.of(
            key=nu.ToStr(elem),
            kind=nu.Str("shape"),
            preview=nu.Str(""),
            navigable=nu.Bool(True),
            vtype=nu.Str(""),
        )
    else:
        row = LensCell(nu.ToStr(elem), ref[elem], nu.Str("leaf"), nu.Bool(True), nu.Bool(False))
    return nu.Let(
        held,
        nu.list(ref.keys()),
        body=_column(
            "mapping",
            nu.Collect(nu.Map(nu.GetItem(keys, nu.Slice(None, max_rows, None)), row, key=item)),
            nu.Len(keys),
        ),
    )


def _sequence_term(ref: StructuredRef, max_rows: int, depth: int) -> nu.Nu:
    """A sequence's elements, capped, keyed by position."""
    held = f"_lens_items{depth}"
    item, elem = _loop(depth)
    items = nu.ListAttrRef(held)
    row = LensCell(
        nu.ToStr(nu.GetItem(elem, nu.Int(0))),
        nu.GetItem(elem, nu.Int(1)),
        nu.Str("leaf"),
        nu.Bool(False),
        nu.Bool(False),
    )
    return nu.Let(
        held,
        nu.Collect(nu.Iter(ref)),
        body=_column(
            "sequence",
            nu.Collect(
                nu.Map(
                    nu.Enumerate(nu.GetItem(items, nu.Slice(None, max_rows, None))),
                    row,
                    key=item,
                )
            ),
            nu.Len(items),
        ),
    )


def _leaf_term(ref: StructuredRef) -> nu.Nu:
    """One value, in full. The only column with a reader pane."""
    return _column(
        "leaf",
        nu.List.of(LensCell(nu.Str("value"), ref, nu.Str("leaf"), nu.Bool(False), nu.Bool(True))),
        nu.Int(1),
    )


def _failed(what: str) -> dict[str, Any]:
    """One column, for a segment that could not be followed or read.

    Same shape as every other column, so the browser needs no second render
    path for it and the cascade stays a list of columns.
    """
    return {
        "kind": "leaf",
        "entries": [
            {
                "key": "error",
                "kind": "leaf",
                "preview": what[:PREVIEW],
                "navigable": False,
                "vtype": "error",
                "text": what[:TEXT],
                "clipped": len(what) > TEXT,
            }
        ],
        "total": 1,
    }


#: :func:`_failed` as an atom, for the failure only a run can find. A column
#: built at construction is a ``Literal``; this one is built from a caught
#: error, so it needs a term.
LensFailed = nu.host(_failed, name="LensFailed")


def _broken(what: str) -> nu.Nu:
    """A column saying the walk did not get there. Keeps the surface answering."""
    return nu.Literal(_failed(what))


def _column_term(root: type[Shape], prefix: tuple[str, ...], max_rows: int, depth: int) -> nu.Nu:
    """The column for whatever ``prefix`` lands on. Protocol dispatch, in python.

    Total by construction: a segment that names nothing yields an error
    column rather than raising, so one bad crumb in a path does not cost the
    browser the columns to its left.
    """
    if not prefix:
        return _shape_term(root, root)
    try:
        ref = _descend(root, prefix)
    except Exception as exc:
        return _broken(f"{'.'.join(prefix)}: {exc!r}")
    if isinstance(ref, ShapeRef):
        return _shape_term(ref._payload["shape_type"], ref)
    if isinstance(ref, (ShapesMappingRef, MappingRef)):
        return _mapping_term(ref, max_rows, depth)
    if isinstance(ref, SequenceRef):
        return _sequence_term(ref, max_rows, depth)
    return _leaf_term(ref)


def column_terms(root: type[Shape], path: object, max_rows: int = DEFAULT_MAX_ROWS) -> nu.Nu:
    """Every column for ``path``: one per prefix, root first.

    Full replacement, not a delta. A navigation is one frame carrying the
    whole cascade, so a browser that missed one is not left holding a stale
    column it can never be told about.
    """
    steps = tuple(str(s) for s in (path or ()))
    cols = [_column_term(root, steps[:i], max_rows, i) for i in range(len(steps) + 1)]
    return nu.List.of(*cols)


def _atomic_column_terms(root: type[Shape], path: object, max_rows: int) -> nu.Nu:
    """:func:`column_terms`, bracketed for atomicity against ``root``.

    The bracket belongs here rather than at the call site because an ``Eval``
    is opaque to the static effect walk: the outer ``auto_flow_atomic`` cannot
    see these reads, so the inner tree has to carry its own.
    """
    return nustd.kv.auto_flow_atomic(column_terms(root, path, max_rows), scope=root)


#: :func:`column_terms` as an atom, so the path can be a value the browser
#: sent. The callable is fixed at class time; the root class rides as a child
#: because it is an address, the same way every ``ops`` call takes one.
LensColumns = nu.host(_atomic_column_terms, name="LensColumns")


def columns(root: type[Shape], path: nu.Nu, *, max_rows: int = DEFAULT_MAX_ROWS) -> nu.Nu:
    """The columns for a path nobody knew at compile time.

    ``Eval`` compiles what :data:`LensColumns` built against the running
    program and drives it in the same ctx, so the reads see the same store
    and the same fabrics as everything else in the arm.

    Guarded, and this one is not the arm's guard doing its job again: a read
    that raises inside the ``Eval`` would leave the arm with nothing to write
    and the browser waiting on a frame that never comes. A cascade always
    comes back, even if all it says is what went wrong.
    """
    return nu.TryCatch(
        nu.Eval(LensColumns(root, path, max_rows), promise={"cardinality": Cardinality.SCALAR}),
        catch=nu.List.of(LensFailed(nu.ToStr(nu.AttrRef("error")))),
    )
