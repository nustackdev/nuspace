"""Addressing a recursive shape at a depth that is only known at run time.

A ref chain cannot express variable depth. Depth is structural: the chain
is a tree and ``_resolve_path`` walks ``children[0]`` a number of times
fixed the moment ``a[x].b[y]`` was written. Every dynamic case in nu is one
*segment* dynamic with the arity pinned.

The substrate underneath has no such limit. ``Navigator.open_at_path`` and
its ensuring twin take a path tuple of any length, and a mem ref just
iterates its keys. Only the Ref API is fixed-arity.

So the path goes in an interaction instead of in the chain. The ref names
the **leaf**, the interaction names the **descent**::

    SetDeep(Page.title, ["a", "b", "c"], "deep")   # set title, 3 levels down
    GetDeep(Page.title, ["a", "b", "c"])           # -> 'deep'
    GetDeep(Page.title, ["a", "zz"])               # -> EMPTY
    GetDeep(Page.title, Space.route)               # path read out of storage

The ref contributes its construct-time prefix; the runtime segments are
spliced in *above* the leaf, with the recursive slot name interleaved,
because recursion goes through a named slot and so each segment costs two
path entries (``pages``, then the key).

That last example is the whole point. The path is an ordinary Nu child, so
it can be a literal, a query, or a Ref read out of storage: a page gets
addressed by a path that arrived from a browser with no python in the loop.

Why these are atoms and not ``-> Nu`` functions: neither can be composed
out of what exists. The ref chain is the only other way to name an address
and it cannot vary its length, so there is no tree to return.

Why ``edge`` is a constructor keyword rather than a child: it names a slot
on a Shape class, which is code, not data. Resolving it at build time is
also what lets the declared view types for the invented levels be read off
the slot, instead of the container layer guessing a default and stamping
the wrong marker on a vivified level. Everything genuinely computable --
the path, the value -- is a child.

Effects are honest but coarse: ``SetDeep`` declares one write on slot 0.
The tree cannot see which addresses were touched, the same price
``ItemPrimitiveGetUnsafe`` pays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nu.engine import Declared
from nu.lang import EMPTY, INVALID, Command, ScalarQuery

from .substrate import substrate_for


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from nu.domains.shape.dsl import Shape
    from nu.domains.shape.refs.base import StructuredRef
    from nu.lang import Nu
    from nu.lang.runtime import Runtime


__all__ = [
    "Descent",
    "GetDeep",
    "SetDeep",
    "descent_for",
]


@dataclass(frozen=True)
class Descent:
    """How one runtime path segment turns into path entries.

    Attributes:
        edge: name of the self-recursive slot the descent goes through.
        edge_marker: declared type marker of that slot (a View class on kv,
            None on substrates that do not carry markers).
        item_marker: declared type marker of one item inside it, read off
            the slot's own item wrapper rather than assumed.
    """

    edge: str
    edge_marker: object
    item_marker: object


def descent_for(ref: StructuredRef, edge: str | None = None) -> Descent:
    """Resolve the recursion edge for a leaf ref, and its declared view types.

    Args:
        ref: the leaf Ref the deep address ends on. Its owning Shape is the
            one that recurses.
        edge: the recursive slot name. Optional when the shape declares
            exactly one; required when it declares several.

    Returns:
        The :class:`Descent` describing one level of the walk.

    Raises:
        TypeError: the ref has no owner shape, the shape declares no (or
            several) recursive slots and none was named, the named slot is
            not on the shape, the slot does not hold the shape itself, or it
            is not a collection that can be keyed into.

    Example:
        >>> descent_for(Page.title).edge
        'pages'
    """
    from .slots import self_slot_names

    shape: type[Shape] | None = ref._owner_shape
    if shape is None:
        msg = (
            f"deep addressing needs the Shape that owns {type(ref).__name__}, "
            f"but this ref carries no owner_shape. Build it from a Shape slot."
        )
        raise TypeError(msg)

    if edge is None:
        names = self_slot_names(shape)
        if len(names) == 1:
            edge = names[0]
        elif not names:
            msg = (
                f"{shape.__name__} declares no self-recursive slot, so there "
                f"is nothing to descend through. Declare one with "
                f"`self_slot(<RefClass>)`, or name an existing slot via edge=."
            )
            raise TypeError(msg)
        else:
            msg = (
                f"{shape.__name__} declares several self-recursive slots "
                f"{names}; name the one to descend through via edge=."
            )
            raise TypeError(msg)

    slots = getattr(shape, "_slots", {})
    slot = slots.get(edge)
    if slot is None:
        msg = f"{shape.__name__} has no slot {edge!r} to descend through."
        raise TypeError(msg)
    if slot.kwargs.get("shape_type") is not shape:
        msg = (
            f"{shape.__name__}.{edge} holds "
            f"{getattr(slot.kwargs.get('shape_type'), '__name__', 'nothing')}, "
            f"not {shape.__name__}. A descent edge must hold the shape itself."
        )
        raise TypeError(msg)

    edge_ref = slot.create_ref(owner_shape=shape)
    wrap = getattr(edge_ref, "_wrap_item_ref", None)
    if wrap is None:
        msg = (
            f"{shape.__name__}.{edge} is a {type(edge_ref).__name__}, which "
            f"cannot be keyed into, so a path segment has nothing to address."
        )
        raise TypeError(msg)
    item_ref = wrap(_PROBE_KEY)
    return Descent(
        edge=edge,
        edge_marker=edge_ref._payload.get("type_marker"),
        item_marker=item_ref._payload.get("type_marker"),
    )


#: Throwaway address used only to mint an item ref and read its declared marker.
_PROBE_KEY = "\x00probe"


def _segments(raw: object) -> tuple[object, ...]:
    """Coerce an evaluated path child into a tuple of segments.

    Args:
        raw: whatever the path slot yielded: a list, a tuple, a View, any
            iterable of keys.

    Returns:
        The segments, root-first. Empty means "address the leaf directly".

    Raises:
        TypeError: the path is a string (iterating it would silently descend
            one level per character) or is not iterable at all.
    """
    if isinstance(raw, (str, bytes)):
        msg = (
            f"deep path must be a sequence of segments, got the string "
            f"{raw!r}. Split it before handing it in."
        )
        raise TypeError(msg)
    try:
        return tuple(raw)  # type: ignore[call-overload]
    except TypeError as exc:
        msg = f"deep path is not iterable: {type(raw).__name__}"
        raise TypeError(msg) from exc


class _DeepAddress:
    """Shared build-time resolution and path splicing for the deep atoms."""

    _children: tuple
    _payload: dict

    def _bind_descent(self, ref: object, edge: str | None) -> None:
        """Resolve the descent edge once, at tree build, and stash it intrinsically."""
        self._payload["descent"] = descent_for(ref, edge)  # type: ignore[arg-type]

    def _splice(self, rt: Runtime, nid: int, segments: Sequence[object]) -> tuple:
        """Full path: the ref's prefix with ``segments`` spliced above the leaf."""
        ref = self._children[0]
        descent: Descent = self._payload["descent"]
        base = ref._resolve_path(rt, rt.program.children[nid][0])
        return substrate_for(ref).splice(
            base, segments, descent.edge, descent.edge_marker, descent.item_marker
        )

    async def _asplice(self, rt: Runtime, nid: int, segments: Sequence[object]) -> tuple:
        """Async twin of :meth:`_splice`; the prefix may hold async children."""
        ref = self._children[0]
        descent: Descent = self._payload["descent"]
        base = await ref._aresolve_path(rt, rt.program.children[nid][0])
        return substrate_for(ref).splice(
            base, segments, descent.edge, descent.edge_marker, descent.item_marker
        )


class GetDeep(_DeepAddress, ScalarQuery):
    """Read the slot-0 leaf Ref at a descent given by the slot-1 path.

    Args:
        ref: the leaf Ref to read. Its owner Shape supplies the recursion.
        path: a sequence of keys, one per level to descend before the leaf.
            An ordinary child, so it may be a literal, a query, or a Ref.
        edge: name of the recursive slot to descend through. Optional when
            the shape declares exactly one.

    Yields:
        The value at the deep address, lifted by the ref. EMPTY when nothing
        is stored there, or when any level of the path is absent. INVALID
        when the path slot itself yields a sentinel.

    Notes:
        - Reads open the path as-is and never vivify, so a missing branch
          stays missing.
        - Slot 0 is never evaluated: the ref supplies its address prefix,
          not its value, so reading it at its own shallow address would be
          a different read entirely.
        - An empty path addresses the leaf directly, the same as reading
          the ref.

    Example:
        >>> run(GetDeep(Page.title, ["a", "b"]), ctx)[0]
        'deep'
    """

    def __init__(self, ref: Nu, path: object, *, edge: str | None = None) -> None:
        super().__init__(ref, path)
        self._bind_descent(ref, edge)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = self._children[0]
        substrate = substrate_for(ref)
        path_thunk = children[1]

        def thunk(rt: Runtime) -> object:
            raw = path_thunk(rt)
            if raw is EMPTY or raw is INVALID:
                return INVALID
            full = self._splice(rt, nid, _segments(raw))
            return substrate.read(ref, rt, full)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = self._children[0]
        substrate = substrate_for(ref)
        path_thunk = children[1]

        async def athunk(rt: Runtime) -> object:
            raw = await path_thunk(rt)
            if raw is EMPTY or raw is INVALID:
                return INVALID
            full = await self._asplice(rt, nid, _segments(raw))
            return await substrate.aread(ref, rt, full)

        return athunk


class SetDeep(_DeepAddress, Command):
    """Write the slot-2 value to the slot-0 leaf Ref at the slot-1 descent.

    Args:
        ref: the leaf Ref to write. Its owner Shape supplies the recursion.
        path: a sequence of keys, one per level to descend before the leaf.
            An ordinary child, so it may be a literal, a query, or a Ref.
        value: the value to store.
        edge: name of the recursive slot to descend through. Optional when
            the shape declares exactly one.

    Notes:
        - Writes vivify: every level along the way is created, each stamped
          with the view type its slot declared rather than the container
          layer's default.
        - ``_mutates`` names slot 0 only. The path and value slots are read,
          not written, and declaring them would pollute the effect fold.
        - Storing a sentinel raises, matching ``SetCmd``.
        - The effect is one write on the ref class. Which addresses were
          touched is not visible to the tree.

    Example:
        >>> run(SetDeep(Page.title, ["a", "b"], "deep"), ctx)
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(
        self, ref: Nu, path: object, value: object, *, edge: str | None = None
    ) -> None:
        super().__init__(ref, path, value)
        self._bind_descent(ref, edge)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = self._children[0]
        substrate = substrate_for(ref)
        path_thunk, value_thunk = children[1], children[2]

        def thunk(rt: Runtime) -> None:
            value = value_thunk(rt)
            if value is EMPTY or value is INVALID:
                raise ValueError("cannot store sentinel value")
            raw = path_thunk(rt)
            if raw is EMPTY or raw is INVALID:
                raise ValueError("cannot write at a sentinel path")
            full = self._splice(rt, nid, _segments(raw))
            substrate.write(ref, rt, full, ref._lower(value))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = self._children[0]
        substrate = substrate_for(ref)
        path_thunk, value_thunk = children[1], children[2]

        async def athunk(rt: Runtime) -> None:
            value = await value_thunk(rt)
            if value is EMPTY or value is INVALID:
                raise ValueError("cannot store sentinel value")
            raw = await path_thunk(rt)
            if raw is EMPTY or raw is INVALID:
                raise ValueError("cannot write at a sentinel path")
            full = await self._asplice(rt, nid, _segments(raw))
            substrate.write(ref, rt, full, await ref._alower(value))

        return athunk
