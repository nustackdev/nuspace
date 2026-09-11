"""Self-recursive shape slots: a shape whose slot holds more of itself.

A page holding child pages, a node holding child nodes. The class body
cannot name its own class, so ``pages = nu.kv.ShapesDictRef.slot(Page)``
inside ``class Page`` is a plain NameError.

The annotation form looks like the answer and is a trap::

    class Node(nu.Shape):
        label: nu.kv.StrRef
        children: nu.kv.ShapesDictRef[str, "Node"]

    Node._slots  # -> {}   every annotation-only slot gone, silently

``ShapeMeta.__new__`` calls ``typing.get_type_hints(cls)`` while the class
is still unbound in its module namespace, catches the NameError and falls
back to ``hints = {}``. Every field declared by annotation alone is then
skipped. Slots assigned explicitly (``x = StrRef.slot()``) are collected
before that and survive, which is what makes it quiet: a class mixing the
two forms loses exactly half of itself and still imports fine.

:func:`self_slot` sidesteps it rather than working around it. Nothing is
annotated, so no name has to resolve. It rides ``__set_name__``, which
Python calls with the finished class object from inside ``type.__new__``:
late enough that the cycle is closed, early enough that ``ShapeMeta``
still stamps its descriptors over the top afterwards.

:class:`RecursiveShape` is ``nu.Shape`` plus a guard that turns the trap
loud: if the annotations on the class cannot resolve, it raises instead of
quietly dropping slots.

Example::

    class Page(RecursiveShape):
        title = nu.kv.StrRef.slot()
        pages = self_slot(nu.kv.ShapesDictRef)

    Page.pages["a"].pages["b"].title   # resolves, arbitrarily deep
"""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING, Any

from nu.domains.shape import Shape
from nu.domains.shape.dsl import ShapeMeta, Slot, SlotDescriptor


if TYPE_CHECKING:
    from nu.domains.shape.refs.base import StructuredRef


__all__ = [
    "RecursiveShape",
    "SelfSlot",
    "self_slot",
    "self_slot_names",
]


#: Marker on ``Slot.props`` identifying a slot minted by :func:`self_slot`.
RECURSIVE_PROP = "nuspace.recursive"


class SelfSlot:
    """A slot declaration that resolves to the class currently being defined.

    Holds the ref class and its ``.slot()`` arguments until ``__set_name__``
    hands over the owner class, then mints the real :class:`Slot` with the
    owner spliced in as the shape type and registers it the way
    ``ShapeMeta`` would have.

    It is deliberately *not* a ``Slot`` subclass: ``ShapeMeta`` collects
    ``Slot`` instances out of the namespace before the class object exists,
    which is the one moment this declaration cannot be resolved at.

    Args:
        ref_cls: the ref class to declare, e.g. ``nu.kv.ShapesDictRef``. Its
            ``slot()`` classmethod is called with the owner class as the
            first positional argument.
        *args: extra positional arguments forwarded to ``ref_cls.slot()``.
        **kwargs: extra keyword arguments forwarded to ``ref_cls.slot()``.

    Notes:
        - Resolution happens once, at class creation. Nothing is lazy and
          nothing depends on the class being bound in its module, so a
          recursive shape defined inside a function works the same.
        - Accessing an unresolved declaration raises rather than handing
          back the marker, so a shape built by some path that skips
          ``__set_name__`` fails loudly at the first read.
        - A subclass inherits the resolved slot as-is, so its children are
          still typed as the base shape. Redeclare ``self_slot`` on the
          subclass when you want the subclass to hold itself.

    Example:
        >>> class Node(RecursiveShape):
        ...     label = nu.kv.StrRef.slot()
        ...     kids = self_slot(nu.kv.ShapesDictRef)
        >>> list(Node._slots)
        ['label', 'kids']
    """

    def __init__(self, ref_cls: type, *args: object, **kwargs: object) -> None:
        self.ref_cls = ref_cls
        self.args = args
        self.kwargs = kwargs
        self.name: str | None = None
        self.slot: Slot | None = None

    def __set_name__(self, owner: type, name: str) -> None:
        """Mint and register the real Slot now that the owner class exists."""
        if not hasattr(owner, "_slots"):
            msg = (
                f"self_slot on {owner.__name__}.{name}: "
                f"{owner.__name__} is not a Shape (no _slots), so there is "
                f"nothing to recurse into."
            )
            raise TypeError(msg)
        factory = getattr(self.ref_cls, "slot", None)
        if factory is None:
            msg = (
                f"self_slot on {owner.__name__}.{name}: "
                f"{self.ref_cls.__name__} has no slot() classmethod."
            )
            raise TypeError(msg)
        slot = factory(owner, *self.args, **self.kwargs)
        if not isinstance(slot, Slot):
            msg = (
                f"self_slot on {owner.__name__}.{name}: "
                f"{self.ref_cls.__name__}.slot() returned "
                f"{type(slot).__name__}, not a Slot."
            )
            raise TypeError(msg)
        slot.name = name
        slot._owner_cls = owner
        slot.props[RECURSIVE_PROP] = True
        self.name = name
        self.slot = slot
        # ``_slots`` is the same dict object ShapeMeta put in the namespace,
        # so writing into it here lands in the class's own slot table and the
        # descriptor pass that follows picks the entry up.
        owner._slots[name] = slot
        setattr(owner, name, SlotDescriptor(name, slot))

    def __get__(self, obj: object, objtype: type | None = None) -> StructuredRef:
        """Loud failure for a declaration that never got resolved."""
        msg = (
            f"self_slot {self.name or '<unnamed>'} was never resolved: "
            f"__set_name__ did not run, so this shape has no recursive slot. "
            f"Declare it in a class body of a Shape."
        )
        raise TypeError(msg)


def self_slot(ref_cls: type, *args: object, **kwargs: object) -> Any:  # noqa: ANN401
    """Declare a slot on a shape that holds that same shape.

    Returns ``Any`` on purpose, the same trick ``ShapeRef.slot`` plays: the
    attribute a checker sees must be the Ref the descriptor hands back, not
    the declaration object that stands in for it until class creation.


    Args:
        ref_cls: the ref class to declare, e.g. ``nu.kv.ShapesDictRef``.
        *args: forwarded to ``ref_cls.slot()`` after the owner class.
        **kwargs: forwarded to ``ref_cls.slot()``.

    Returns:
        A :class:`SelfSlot` declaration. It replaces itself with a real
        ``Slot`` plus descriptor at class creation.

    Example:
        >>> class Page(RecursiveShape):
        ...     title = nu.kv.StrRef.slot()
        ...     pages = self_slot(nu.kv.ShapesDictRef)
        >>> _ = Page.pages["a"].pages["b"].title
    """
    return SelfSlot(ref_cls, *args, **kwargs)


def self_slot_names(shape: type) -> tuple[str, ...]:
    """Names of the self-recursive slots declared on ``shape``, in order.

    Args:
        shape: a Shape class.

    Returns:
        The slot names minted by :func:`self_slot`, empty when there are none.

    Example:
        >>> self_slot_names(Page)
        ('pages',)
    """
    slots = getattr(shape, "_slots", {})
    return tuple(n for n, s in slots.items() if s.props.get(RECURSIVE_PROP))


class RecursiveShapeMeta(ShapeMeta):
    """``ShapeMeta`` that refuses to silently drop annotation-declared slots.

    ``ShapeMeta`` swallows the NameError from ``typing.get_type_hints`` and
    carries on with no hints, which drops every annotation-only slot on the
    class. This subclass re-runs the same call and raises instead, naming
    the class and pointing at :func:`self_slot`.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, object],
        **kwargs: object,
    ) -> type:
        """Build the Shape, then verify its annotations actually resolved."""
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        own = namespace.get("__annotations__") or {}
        if own:
            try:
                typing.get_type_hints(cls)
            except NameError as exc:
                msg = (
                    f"{name}: an annotation on this Shape does not resolve "
                    f"({exc}). ShapeMeta drops every annotation-declared slot "
                    f"when that happens, leaving the class silently gutted. "
                    f"For a slot holding {name} itself use "
                    f"`self_slot(<RefClass>)`; otherwise fix the annotation."
                )
                raise TypeError(msg) from exc
        return cls


class RecursiveShape(Shape, metaclass=RecursiveShapeMeta):
    """A Shape that may hold itself, with the silent-wipe trap made loud.

    Identical to ``nu.Shape`` except that an unresolvable annotation raises
    at class creation instead of quietly emptying ``_slots``. Pair it with
    :func:`self_slot` for the recursive slot itself.

    Example::

        class Page(RecursiveShape):
            title = nu.kv.StrRef.slot()
            pages = self_slot(nu.kv.ShapesDictRef)
    """
