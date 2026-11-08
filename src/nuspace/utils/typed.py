"""A ref read through a Shape: each of the Shape's slots placed under it with ``with_parent``.

State's levels are empty Shapes (a cell's scope, a content item), so a
program's own Shape sits on one through ``with_parent``.
:class:`Typed` spells that once: ``Typed(State.cells[c], Counter).value``
is ``Counter.value.with_parent(State.cells[c])``. :class:`TypedItems` is a
mapping whose items are read so: ``TypedItems(entries, Note)["a"].body`` is
``Note.body.with_parent(entries["a"])``.

Generic: nothing here knows a plane. Both build refs and read nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nu.domains.shape import StructuredRef


if TYPE_CHECKING:
    import nu


__all__ = ["Typed", "TypedItems"]


class Typed:
    """``ref`` read through ``shape``: a slot of ``shape`` is that slot placed under ``ref``.

    ``.value`` (or ``["value"]``) is ``shape.value.with_parent(ref)``, a
    fresh ref each time. A name ``shape`` has no slot for is ``ref``'s own,
    so ``.erase()``, ``.exists()``, ``.extract()`` act on the whole level. A
    slot never shadows a ref verb: nu refuses one at class build.

    Args:
        ref: The level, a shape ref.
        shape: The Shape it is read through.
    """

    __slots__ = ("_ref", "_shape")

    def __init__(self, ref: StructuredRef, shape: type[nu.Shape]) -> None:
        self._ref = ref
        self._shape = shape

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)
        slot = getattr(self._shape, name, None)
        if isinstance(slot, StructuredRef):
            return slot.with_parent(self._ref)
        return getattr(self._ref, name)

    def __getitem__(self, name: str) -> object:
        return self.__getattr__(name)

    def __reduce__(self) -> tuple[object, ...]:
        return (type(self), (self._ref, self._shape))

    def __repr__(self) -> str:
        return f"<{self._shape.__name__} at {self._ref!r}>"


class TypedItems:
    """A mapping ref whose items are each read through ``shape``: ``[key]`` is a :class:`Typed`.

    Any other name is the mapping's own: ``.keys()``, ``.exists()``,
    ``.on_children_change()``.

    Args:
        ref: The mapping, a dict ref.
        shape: The Shape each item is read through.
    """

    __slots__ = ("_ref", "_shape")

    def __init__(self, ref: StructuredRef, shape: type[nu.Shape]) -> None:
        self._ref = ref
        self._shape = shape

    def __getitem__(self, key: nu.StrArg) -> Typed:
        return Typed(self._ref[key], self._shape)

    def __getattr__(self, name: str) -> object:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._ref, name)

    def __reduce__(self) -> tuple[object, ...]:
        return (type(self), (self._ref, self._shape))

    def __repr__(self) -> str:
        return f"<{self._shape.__name__} items at {self._ref!r}>"
