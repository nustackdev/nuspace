"""Turning a ref into a column.

## The kind table

A lens dispatches on the shape of the data it is pointed at. That is not
an incidental ``if`` chain it should be refactored out of -- it is the
job. What was worth fixing is that the dispatch was written twice, once
as ``issubclass`` over a slot's declared ref class and once as
``isinstance`` over a live ref, in two different orders, with no way to
notice if the two ever disagreed.

So it is written once, as an ordered table of ``(ref class, kind)``, and
both callers walk it. ``nu.inspect.taxonomy.kind_of`` places a Nu class
the same way: an ordered tuple of bases and a walk for the most specific
match. The five ref classes here happen to be disjoint, so the order is
documentation rather than precedence -- but that is a fact about nu
today, not a promise, and a table keeps one answer when it changes.

``KIND_BUILDERS`` then maps the kind token to the function that fills a
column of it. Adding a ref class is one row in each table; there is no
third place that has to hear about it.

## Scope

The builders need three things that have nothing to do with which ref
they were handed: the Context to evaluate against, the root Shape class
to scope the kv bracket to, and the row cap. ``Scope`` carries them so
the builders share one signature and the dispatch table can be a dict.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import nu
from nu.domains.shape.refs.item import ItemRef
from nu.domains.shape.refs.mapping import MappingRef
from nu.domains.shape.refs.sequence import SequenceRef
from nu.domains.shape.refs.shape import ShapeRef
from nu.domains.shape.refs.shapes_mapping import ShapesMappingRef
from nu.kv.tree import auto_flow_atomic
from nuspace.web.refs.lens.values import full_text, preview, vtype


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from nu.domains.shape import Shape
    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang import Context


__all__ = ["KIND_TABLE", "Scope", "all_columns", "column_for", "descend", "kind_of"]


log = logging.getLogger("nuspace.refs")


# Ref class -> the column kind a row of it opens. Most specific first.
KIND_TABLE: tuple[tuple[type, str], ...] = (
    (ShapesMappingRef, "mapping"),
    (MappingRef, "mapping"),
    (SequenceRef, "sequence"),
    (ShapeRef, "shape"),
    (ItemRef, "leaf"),
)

# What a row leads to when the table has nothing to say about its class.
# A leaf is the honest default: something is there, we just cannot walk
# into it, so the lens offers to show its value.
FALLBACK_KIND = "leaf"


@dataclass(frozen=True)
class Scope:
    """Everything a column builder needs that is not the ref itself."""

    ctx: Context
    root: type[Shape]
    max_rows: int

    async def run(self, term: nu.Nu) -> Any:  # noqa: ANN401 -- kv values are opaque
        """Evaluate one term against this space's storage."""
        value, _ = await nu.arun(auto_flow_atomic(term, scope=self.root), self.ctx)  # type: ignore[arg-type]
        return value


def kind_of(ref_cls: type) -> str:
    """The column kind ``ref_cls`` opens, or ``"unknown"``."""
    for base, kind in KIND_TABLE:
        if issubclass(ref_cls, base):
            return kind
    return "unknown"


def descend(root: type[Shape], path: tuple[str, ...]) -> StructuredRef:
    """Build the substrate ref at ``path`` from the root Shape class."""
    if not path:
        raise ValueError("descend needs at least one segment")
    ref = getattr(root, path[0])
    for seg in path[1:]:
        ref = ref[seg]
    return ref


# -- builders, one per kind --------------------------------------------------


async def shape_column(ref: StructuredRef, scope: Scope) -> dict[str, Any]:
    """A Shape's slot list. Declaration only, no kv touch."""
    del scope
    return _shape_slots(ref._payload["shape_type"])


async def mapping_column(ref: StructuredRef, scope: Scope) -> dict[str, Any]:
    """A mapping's keys, capped at ``max_rows``."""
    raw = await scope.run(nu.Collect(nu.Iter(ref)))
    keys = list(raw or [])
    total = len(keys)
    entries = [
        {"key": str(k), "kind": "shape", "preview": "", "navigable": True, "vtype": ""}
        for k in keys[: scope.max_rows]
    ]
    return {"kind": "mapping", "entries": entries, "total": total}


async def sequence_column(ref: StructuredRef, scope: Scope) -> dict[str, Any]:
    """A sequence's values, indexed and capped."""
    raw = await scope.run(nu.Collect(nu.Iter(ref)))
    values = list(raw or [])
    total = len(values)
    entries = [
        {
            "key": str(i),
            "kind": "leaf",
            "preview": preview(v),
            "navigable": True,
            "vtype": vtype(v),
        }
        for i, v in enumerate(values[: scope.max_rows])
    ]
    return {"kind": "sequence", "entries": entries, "total": total}


async def leaf_column(ref: StructuredRef, scope: Scope) -> dict[str, Any]:
    """One row: this leaf's current value, in full.

    A read that blows up is a row, not a traceback. An address through a
    missing container raises and a lens is exactly the tool you reach for
    when you suspect that, so the error is what it has to show.
    """
    try:
        value = await scope.run(ref)
        kind = vtype(value)
    except Exception as exc:
        value = f"<error: {exc!r}>"
        kind = "error"
    text, clipped = full_text(value)
    entry = {
        "key": "value",
        "kind": "leaf",
        "preview": preview(value),
        "navigable": False,
        "vtype": kind,
        "text": text,
        "clipped": clipped,
    }
    return {"kind": "leaf", "entries": [entry], "total": 1}


KIND_BUILDERS: dict[str, Callable[[StructuredRef, Scope], Awaitable[dict[str, Any]]]] = {
    "shape": shape_column,
    "mapping": mapping_column,
    "sequence": sequence_column,
    "leaf": leaf_column,
}


# -- dispatch ----------------------------------------------------------------


async def column_for(path: tuple[str, ...], scope: Scope) -> dict[str, Any]:
    """The column the last segment of ``path`` opens.

    The empty path is the root Shape *class*, which is not a ref and has
    no instance to place in the table, so it is answered directly.
    """
    if not path:
        return _shape_slots(scope.root)
    ref = descend(scope.root, path)
    build = KIND_BUILDERS.get(kind_of(type(ref)), KIND_BUILDERS[FALLBACK_KIND])
    return await build(ref, scope)


async def all_columns(path: tuple[str, ...], scope: Scope) -> list[dict[str, Any]]:
    """The cascade: one column per prefix of ``path``, root included.

    A segment that does not resolve ends the walk and the caller gets the
    prefix that did. ``descend`` raises on a name the Shape has not got,
    and a lens is the tool you reach for precisely when you are not sure
    what is there -- so the answer is how far it got, not nothing at all.
    The path the caller ships back has to be trimmed to match.
    """
    out = [await column_for((), scope)]
    for i in range(1, len(path) + 1):
        try:
            out.append(await column_for(path[:i], scope))
        except Exception:
            log.warning("lens: %r does not resolve, stopping at %r", path, path[: i - 1])
            break
    return out


def _shape_slots(shape_cls: type[Shape]) -> dict[str, Any]:
    """A Shape class's declared slots as rows.

    A slot is a declaration, not a value: nothing has been read yet, so
    every row types as ``ref`` and the browser renders the ref class name
    as a type tag rather than as a value.
    """
    entries = [
        {
            "key": name,
            "kind": kind_of(slot.ref_cls),
            "preview": slot.ref_cls.__name__,
            "navigable": True,
            "vtype": "ref",
        }
        for name, slot in shape_cls._slots.items()
    ]
    return {"kind": "shape", "entries": entries, "total": len(entries)}
