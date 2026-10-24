"""Content: typed, findable items any cell can write, read and show.

A prog is code, content is data. A kind is a :class:`Content` over a plain
``nu.Shape``, its schema, read off the generic argument at run time::

    class Text(nu.Shape):
        value = nustd.kv.StrRef.slot()


    class TextContent(nuspace.Content[Text]):
        @classmethod
        def match(cls, item: Text, *, text: nu.StrArg | Unset = UNSET) -> nu.Bool: ...

A kind is registered through an extension (``Extension(contents=...)``) and
named by its importable name, module then qualified name
(:func:`kind_name`), so a worker imports it from the name alone
(:func:`load_kind`).

An item lives in nuspace's store, never in a program's own state, at a
fixed place per kind and scope (:mod:`nuspace.shapes.contents`). Its
address is plain data, ``(kind, scope, id)``, a scope being ``(level, id)``
with the level one of :data:`CELL`, :data:`PLANE` and :data:`SPACE`::

    TextContent.cell("summary")           # this cell's item "summary", a Text
    TextContent.plane("title")            # this plane's
    TextContent.space("readme")           # the space's
    TextContent.at(("cell", c), "summary")  # any item, by its address

``cell`` and ``plane`` are relative, like ``CellState`` and ``PlaneState``:
the kernel lands them under the cell and plane running the program
(:mod:`nuspace.shapes.reroot`). Every accessor is typed to return the
kind's Shape, as a ``DictRef[K, S][key]`` is, so fields chain as on any
Shape.

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import importlib
import inspect
import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast, get_args, get_origin

import nu
import nustd.kv
from nu.engine import Declared
from nu.lang import ScalarQuery
from nu.lang.sentinels import UNSET, Unset
from nu.lang.typeinfo import TypeInfo
from nuspace.shapes import CONTENT_KIND, CellContent, PlaneContent, States
from nustd.ui.core import Ref as UiRef


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import StructuredRef
    from nu.lang.runtime import Runtime


__all__ = [
    "CELL",
    "INPUTS",
    "LEVELS",
    "NUMBER_INPUT",
    "PLANE",
    "SPACE",
    "SWITCH_INPUT",
    "TEXT_INPUT",
    "UNSET",
    "Content",
    "Drawing",
    "SearchField",
    "Unset",
    "info",
    "kind_name",
    "load_kind",
]


S = TypeVar("S", bound=nu.Shape)


#: A scope's level: one cell's items.
CELL = "cell"

#: A plane's own items.
PLANE = "plane"

#: The space's own items. Its scope id is ``""``.
SPACE = "space"

#: Every level, narrowest first: the order a search walks them in.
LEVELS = (CELL, PLANE, SPACE)

#: The :class:`~nuspace.shapes.contents.KindContents` slot each scoped level is under.
_SLOTS = {CELL: "cells", PLANE: "planes"}

#: A search field's inputs: a text box, a number input, a switch.
TEXT_INPUT = "text"
NUMBER_INPUT = "number"
SWITCH_INPUT = "switch"
INPUTS = (TEXT_INPUT, NUMBER_INPUT, SWITCH_INPUT)

#: A ``match`` keyword's annotation, read as words, to the input it gets. First hit wins.
_ANNOTATED = (
    (re.compile(r"\b(BoolArg|bool|Bool)\b"), SWITCH_INPUT),
    (re.compile(r"\b(FloatArg|float|Float|IntArg|int|Int)\b"), NUMBER_INPUT),
)


@dataclass(frozen=True)
class SearchField:
    """One field of a kind's search form: the ``match`` keyword it fills and how it is asked.

    Args:
        name: The keyword.
        input: :data:`TEXT_INPUT`, :data:`NUMBER_INPUT` or :data:`SWITCH_INPUT`.
        label: What the form shows beside it.
    """

    name: str
    input: str = TEXT_INPUT
    label: str = ""


def kind_name(kind: type[Content[Any]]) -> str:
    """A kind's name: its importable name, ``nuverse.contents.text.TextContent``."""
    return f"{kind.__module__}.{kind.__qualname__}"


def load_kind(name: str) -> type[Content[Any]]:
    """The kind a :func:`kind_name` names, imported: the longest module prefix, then attributes.

    Raises:
        ImportError: No prefix of ``name`` is a module.
        AttributeError: The module has no such class.
        TypeError: What it names is not a kind.
    """
    parts = name.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        try:
            found: object = importlib.import_module(".".join(parts[:cut]))
        except ImportError:
            continue
        for part in parts[cut:]:
            found = getattr(found, part)
        if not (isinstance(found, type) and issubclass(found, Content)):
            msg = f"{name!r} is not a kind: {found!r}"
            raise TypeError(msg)
        return found
    msg = f"No module to import kind {name!r} from"
    raise ImportError(msg)


def _input(annotation: object) -> str:
    """The input a ``match`` keyword annotated so gets: a switch, a number, or text."""
    if annotation is inspect.Parameter.empty:
        return TEXT_INPUT
    spelled = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    spelled = spelled or str(annotation)
    for words, given in _ANNOTATED:
        if words.search(spelled):
            return given
    return TEXT_INPUT


def _label(name: str) -> str:
    """A keyword as a form says it: ``min_loss`` as ``Min loss``."""
    return name.replace("_", " ").strip().capitalize()


def _item(
    parent: StructuredRef | None, item_id: nu.StrArg, schema: type[S], owner: type[nu.Shape]
) -> S:
    """The ref to one item of ``schema`` at ``item_id`` under ``parent``, typed as ``schema``.

    What a ``DictRef`` of the Shape hands out for a key, built here because
    the store's containers are one type for every kind.
    """
    ref = nustd.kv.ShapeRef(item_id, shape_type=schema, parent_ref=parent, owner_shape=owner)
    ref._payload["type_info"] = TypeInfo.from_annotation(schema)
    return cast("S", ref)


class Content(Generic[S]):
    """A kind: the behaviors of one kind of item and the schema they read. Not a Shape.

    Subclass it over the schema, ``class TextContent(Content[Text])``, and
    register it in an extension. Every behavior is a classmethod; a kind is
    never instantiated.

    Behaviors:

    - :meth:`match`, the question, as keyword arguments. The item's own
      logic: it works anywhere. A keyword left out stays ``UNSET``, so
      ``match`` branches on it at construction and the term it builds holds
      only the checks asked for.
    - :meth:`render`, :meth:`render_hit`: how an item draws in full and as a
      search hit. Bare ui chains, landed under wherever the drawing goes
      (:class:`Drawing`).
    - :meth:`form`: the search form, generated from ``match``'s keywords.

    Attributes:
        label: What the search ui calls the kind. Empty takes the class name,
            less a trailing ``Content``.
    """

    label: ClassVar[str] = ""

    @classmethod
    def schema(cls) -> type[S]:
        """The kind's Shape: the argument ``Content[...]`` was given, here or in a base.

        Raises:
            TypeError: The class names none, eg a generic base kind.
        """
        for klass in cls.__mro__:
            for base in getattr(klass, "__orig_bases__", ()):
                origin = get_origin(base)
                if isinstance(origin, type) and issubclass(origin, Content):
                    (arg,) = get_args(base)
                    if isinstance(arg, type) and issubclass(arg, nu.Shape):
                        return cast("type[S]", arg)
        msg = f"{cls.__qualname__} names no schema: subclass Content[YourShape]"
        raise TypeError(msg)

    @classmethod
    def title(cls) -> str:
        """:attr:`label`, or the class name less a trailing ``Content``."""
        if cls.label:
            return cls.label
        name = cls.__name__
        return name[: -len("Content")] if name.endswith("Content") and name != "Content" else name

    # --- Behaviors ---------------------------------------------------------------

    @classmethod
    def match(cls, item: S) -> nu.Bool:
        """Whether ``item`` answers the question. Override it, adding keyword-only arguments.

        Each keyword is one part of the question, defaulting to ``UNSET``,
        and is a field of the search form (:meth:`form`). The default asks
        nothing, so every item of the kind matches: a kind with no question
        lists all its items.
        """
        return nu.Bool(True)

    @classmethod
    def render(cls, item: S) -> nu.Nu:
        """``item`` drawn in full, as bare ui chains. Draws nothing by default."""
        return nu.Noop()

    @classmethod
    def render_hit(cls, item: S) -> nu.Nu:
        """``item`` drawn as one search hit, as bare ui chains. Draws nothing by default."""
        return nu.Noop()

    @classmethod
    def form(cls) -> tuple[SearchField, ...]:
        """The search form: one field per keyword of :meth:`match`, in order.

        A keyword annotated with ``BoolArg`` (or ``bool``) is a switch, one
        with ``FloatArg`` or ``IntArg`` (or ``float``, ``int``) a number
        input, any other a text box. Override it to ask otherwise; each
        field's ``name`` is the keyword it fills.
        """
        params = list(inspect.signature(cls.match).parameters.values())[1:]
        named = (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        return tuple(
            SearchField(p.name, _input(p.annotation), _label(p.name))
            for p in params
            if p.kind in named
        )

    # --- Accessors ---------------------------------------------------------------

    @classmethod
    def cell(cls, item_id: nu.StrArg) -> S:
        """The running cell's item ``item_id``. Relative: lands under the cell at load."""
        ref = _item(None, item_id, cls.schema(), CellContent)
        ref._payload[CONTENT_KIND] = kind_name(cls)  # type: ignore[attr-defined]
        return ref

    @classmethod
    def plane(cls, item_id: nu.StrArg) -> S:
        """The running plane's own item ``item_id``. Relative: lands under the plane at load."""
        ref = _item(None, item_id, cls.schema(), PlaneContent)
        ref._payload[CONTENT_KIND] = kind_name(cls)  # type: ignore[attr-defined]
        return ref

    @classmethod
    def space(cls, item_id: nu.StrArg) -> S:
        """The space's own item ``item_id``."""
        return _item(States.contents[kind_name(cls)].space, item_id, cls.schema(), States)

    @classmethod
    def at(cls, scope: tuple[str, nu.StrArg], item_id: nu.StrArg) -> S:
        """Any item of the kind, by its address.

        Args:
            scope: ``(level, id)``: ``(CELL, cell id)``, ``(PLANE, plane id)``
                or ``(SPACE, "")``. The level is a python str, so the ref's
                path is known when it is built; the id may be any ``StrArg``.
            item_id: The item's id in that scope.

        Raises:
            ValueError: The level is none of :data:`LEVELS`.
        """
        level, scope_id = scope
        if level == SPACE:
            return cls.space(item_id)
        if level not in _SLOTS:
            msg = f"scope level {level!r} is none of {LEVELS}"
            raise ValueError(msg)
        held = getattr(States.contents[kind_name(cls)], _SLOTS[level])[scope_id]
        return _item(held, item_id, cls.schema(), States)


def info(kind: type[Content[Any]]) -> dict[str, Any]:
    """What space info keeps of a kind for the search ui: ``{label, fields}``, plain data."""
    return {"label": kind.title(), "fields": [asdict(f) for f in kind.form()]}


def _drawn_ui(ref: StructuredRef) -> bool:
    """A ``rooted`` predicate: every chain but a bare ui one stays where it is."""
    return not isinstance(ref, UiRef)


class Drawing(ScalarQuery):
    """The term drawing one item by its address, landed under ``under``. Run it with ``nu.Eval``.

    For a program that learns which item to draw only at run time (eg a
    search hit): the kind is imported by name, the item reached with
    :meth:`Content.at`, and its :meth:`~Content.render` (or
    :meth:`~Content.render_hit`) term built, its bare ui chains spliced
    under ``under``. ``under`` is a ref the program names bare like any of
    its ui refs: it sits in a structural slot, never read, so the program's
    own rewrites land it first and the drawing lands where it does.

    Args:
        kind: The kind's name.
        level: The scope's level, one of :data:`LEVELS`.
        scope: The scope's id, ``""`` for the space.
        item_id: The item's id.
        under: A ui ref the drawing lands under.
        hit: Draw ``render_hit`` rather than ``render``.

    Yields:
        The drawing, a term: ``nu.Eval(Drawing(...))`` draws it. It reads the
        item bare, so its caller brackets it, as any read:
        ``ops.snapshot(nu.Eval(Drawing(...)))``.
    """

    _structural = Declared(value=frozenset({4}), name="structural")

    def __init__(
        self,
        kind: nu.StrArg,
        level: nu.StrArg,
        scope: nu.StrArg,
        item_id: nu.StrArg,
        under: nu.Nu,
        *,
        hit: bool = False,
    ) -> None:
        super().__init__(kind, level, scope, item_id, under)
        self._payload["hit"] = hit

    def _term(self, kind: object, level: object, scope: object, item_id: object) -> nu.Nu:
        found = load_kind(str(kind))
        item = found.at((str(level), str(scope)), str(item_id))
        drawn = found.render_hit(item) if self._payload["hit"] else found.render(item)
        return nu.shape.reroot(drawn, self._children[4], rooted=_drawn_ui)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, level, scope, item_id = children[:4]

        def thunk(rt: Runtime) -> object:
            return self._term(kind(rt), level(rt), scope(rt), item_id(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, level, scope, item_id = children[:4]

        async def athunk(rt: Runtime) -> object:
            return self._term(await kind(rt), await level(rt), await scope(rt), await item_id(rt))

        return athunk
