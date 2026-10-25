"""Content: typed, findable items any cell can write, read and show.

A prog is code, content is data. A kind is a :class:`Content` over a plain
``nu.Shape``, its schema, read off the generic argument at run time::

    class Text(nu.Shape):
        value = nustd.kv.StrRef.slot()


    class TextContent(nuspace.Content[Text], name="Text"):
        @classmethod
        def match(cls, item: Text, *, text: nu.StrArg | Unset = UNSET) -> nu.Bool: ...

A kind declares its name on the class, by convention the class's own less
``Content``, and an installed package registers it with a
:class:`~nuspace.ext.ContentSpec` in its extension
(``Extension(contents=(ContentSpec(TextContent),))``), which says how a
space presents it: its label, description and icon. Registered, it is named
``<package>.<name>``, ``nuverse.Text``, like a Plane or a Cell
(:func:`kind_name`). The store and every address key by that name, never by
where the class lives, so moving a module leaves items in place. Any
process, a worker too, finds the spec a name names, and the kind through
it, from the installed entry points (:func:`~nuspace.ext.content_spec`): a
headless op needs the name only, never a host's registry.

An item lives in nuspace's store, never in a program's own state, at a
fixed place per kind and scope (:mod:`nuspace.shapes.contents`). Its
address is plain data, ``(kind, scope, id)``, a scope being ``(level, id)``
with the level one of :data:`CELL`, :data:`PLANE` and :data:`SPACE`::

    TextContent.cell("summary")           # this cell's item "summary", a Text
    TextContent.plane("title")            # this plane's
    TextContent.space("readme")           # the space's
    TextContent.at(("cell", c), "summary")  # any item, by its address
    TextContent.items(("cell", c))        # every item of a scope, by id
    TextContent.new(("cell", c), into=r)  # a fresh item, its id set in r
    TextContent.find(text="basil")        # (address, item) of every match

``cell`` and ``plane`` are relative, like ``CellState`` and ``PlaneState``:
the kernel lands them under the cell and plane running the program
(:mod:`nuspace.shapes.reroot`). Every accessor is typed to return the
kind's Shape, as a ``DictRef[K, S][key]`` is, so fields chain as on any
Shape.

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast, get_args, get_origin

import nu
import nustd.kv
from nu.engine import Declared
from nu.lang import ScalarQuery
from nu.lang.sentinels import UNSET, Unset
from nu.lang.typeinfo import TypeInfo
from nuspace.ext.registry import content_spec, kind_name
from nuspace.shapes import CONTENT_KIND, CellContent, PlaneContent, States
from nustd.ui.core import Ref as UiRef


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from nu.domains.shape import StructuredRef
    from nu.lang.runtime import Runtime


__all__ = [
    "CELL",
    "INPUTS",
    "ITEM_PREFIX",
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
    "address",
    "kind_name",
    "matched",
    "scopes",
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

#: What the ids :meth:`Content.new` mints start with.
ITEM_PREFIX = "i"

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


def _item(item_id: nu.StrArg, schema: type[S], owner: type[nu.Shape]) -> S:
    """A relative chain's root: the item ``item_id`` of ``schema``, rooted at ``owner``, typed as ``schema``.

    What a ``DictRef`` of the Shape hands out for a key, built here because
    a relative chain has no parent until the kernel lands it.
    """
    ref = nustd.kv.ShapeRef(item_id, shape_type=schema, parent_ref=None, owner_shape=owner)
    ref._payload["type_info"] = TypeInfo.from_annotation(schema)
    return cast("S", ref)


def _level(scope: tuple[str, nu.StrArg]) -> tuple[str, nu.StrArg]:
    """``scope`` checked: its level one of :data:`LEVELS`.

    Raises:
        ValueError: The level is none of :data:`LEVELS`.
    """
    level, scope_id = scope
    if level not in LEVELS:
        msg = f"scope level {level!r} is none of {LEVELS}"
        raise ValueError(msg)
    return level, scope_id


def address(
    kind: str | type[Content[Any]], scope: tuple[str, nu.StrArg], item_id: nu.StrArg
) -> nu.Dict:
    """An item's address as plain data: ``{"kind": name, "scope": [level, id], "id": item id}``.

    What a search hit, :meth:`Content.find` and a cell linking to an item
    keep. Read it back with :func:`~nuspace.ext.content_spec` and
    :meth:`Content.at`.

    Args:
        kind: The kind, or its name.
        scope: ``(level, id)``, as :meth:`Content.at` takes it.
        item_id: The item's id in that scope.
    """
    name = kind if isinstance(kind, str) else kind_name(kind)
    level, scope_id = scope
    return nu.Dict.of(kind=name, scope=nu.List.of(level, scope_id), id=item_id)


class Content(Generic[S]):
    """A kind: the behaviors of one kind of item and the schema they read. Not a Shape.

    Subclass it over the schema, ``class TextContent(Content[Text], name="Text")``,
    and register it in an extension with a :class:`~nuspace.ext.ContentSpec`,
    which says how a space presents it. Every behavior is a classmethod; a
    kind is never instantiated.

    Behaviors:

    - :meth:`match`, the question, as keyword arguments. The item's own
      logic: it works anywhere. A keyword left out stays ``UNSET``, so
      ``match`` branches on it at construction and the term it builds holds
      only the checks asked for.
    - :meth:`render`, :meth:`render_hit`: how an item draws in full and as a
      search hit. Bare ui chains, landed under wherever the drawing goes
      (:class:`Drawing`).
    - :meth:`form`: the search form, generated from ``match``'s keywords.

    Every kind names itself, ``class TextContent(Content[Text], name="Text")``:
    its identity in the store, so one word, no dots, by convention the class
    name less ``Content``. Installed, its package goes in front
    (:func:`kind_name`).

    Attributes:
        name: The name, as declared.

    Raises:
        TypeError: A subclass declares no name.
        ValueError: The name is empty or has a dot.
    """

    name: ClassVar[str] = ""

    def __init_subclass__(cls, name: str | None = None, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if name is None:
            msg = (
                f"{cls.__qualname__} declares no name: class {cls.__name__}(Content[...], name=...)"
            )
            raise TypeError(msg)
        if not name or "." in name:
            msg = f"{cls.__qualname__}: a kind's name is one word with no dots, not {name!r}"
            raise ValueError(msg)
        cls.name = name

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
        ref = _item(item_id, cls.schema(), CellContent)
        ref._payload[CONTENT_KIND] = kind_name(cls)  # type: ignore[attr-defined]
        return ref

    @classmethod
    def plane(cls, item_id: nu.StrArg) -> S:
        """The running plane's own item ``item_id``. Relative: lands under the plane at load."""
        ref = _item(item_id, cls.schema(), PlaneContent)
        ref._payload[CONTENT_KIND] = kind_name(cls)  # type: ignore[attr-defined]
        return ref

    @classmethod
    def space(cls, item_id: nu.StrArg) -> S:
        """The space's own item ``item_id``."""
        return cls.at((SPACE, ""), item_id)

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
        return cast("S", cls.items(scope)[item_id])

    @classmethod
    def items(cls, scope: tuple[str, nu.StrArg]) -> nustd.kv.DictRef[str, S]:
        """One scope's items of the kind, by id: a ``DictRef[str, S]`` in the kind's own layout.

        ``items(scope)[id]`` is :meth:`at`. The mapping is the store's own, so
        ``keys``, ``len``, ``contains`` and ``on_children_change`` read and
        watch storage, a write lands an item and ``items(scope)[id].erase()``
        removes one. Not relative: name the running cell as
        ``(CELL, ops.Here.cell)``.

        Args:
            scope: ``(level, id)``, as :meth:`at` takes it.

        Raises:
            ValueError: The level is none of :data:`LEVELS`.
        """
        level, scope_id = _level(scope)
        held = States.contents[kind_name(cls)]
        parent, at = (held, "space") if level == SPACE else (getattr(held, _SLOTS[level]), scope_id)
        ref = nustd.kv.DictRef(at, parent_ref=parent, owner_shape=States)
        ref._payload["type_info"] = TypeInfo.from_annotation(dict[str, cls.schema()])
        return ref

    @classmethod
    def new(cls, scope: tuple[str, nu.StrArg], *, into: nu.Ref | None = None) -> nu.Nu:
        """A new item in ``scope``: a fresh id minted, the item written empty, the id set in ``into``.

        The id is time ordered (:data:`ITEM_PREFIX`, then the moment it was
        minted), so a scope's ids sort the way its items were made. Written
        empty, the item is there at once: :meth:`items` lists it before any
        field is set. Its address is ``(kind, scope, id)``. Bare, as any
        write: its caller brackets it, eg with ``ops.atomic_state``::

            made = RowContent.new(scope, into=Local.id)
            fill = RowContent.at(scope, nu.Str(Local.id)).cells["name"].set("Basil")
            ops.atomic_state(made >> fill)

        Args:
            scope: ``(level, id)``, as :meth:`at` takes it.
            into: A ref set to the new id, for the writes after. None to only
                make the item.
        """
        from nuspace.ops.utils import MintId

        items = cls.items(scope)

        def made(minted: nu.ObjectRef) -> nu.Nu:
            item_id = nu.Str(minted)
            kept = into.set(item_id) if into is not None else nu.Noop()
            return items[item_id].set({}) >> kept

        return nu.let(MintId(ITEM_PREFIX), made)

    @classmethod
    def find(cls, **question: Any) -> nu.Nu:  # noqa: ANN401
        """Every item of the kind :meth:`match` holds for, from every scope: the Search plane's walk.

        Cells first, then planes, then the space's, as a search walks them
        (:func:`scopes`, :func:`matched`). The keywords are :meth:`match`'s;
        one left out stays ``UNSET``, so asked nothing every item ``match``
        lets through is found. A read, bare: its caller brackets it, eg with
        ``ops.snapshot``.

        Yields:
            A list of ``(address, item)`` pairs: the item's :func:`address`
            and its fields, plain data.
        """
        name = kind_name(cls)

        def scope_pairs(level: str, scope_id: nu.StrArg) -> nu.Nu:
            scope = (level, scope_id)

            def pair(found: nu.Attr) -> nu.Nu:
                item_id = nu.Str(found)
                return nu.Tuple.of(address(name, scope, item_id), cls.at(scope, item_id).extract())

            return matched(cls, scope, question).map(pair).to_list()

        def level_pairs(level: str) -> nu.Nu:
            each = scopes(cls, level).iter().map(lambda at: scope_pairs(level, nu.Str(at)))
            return each.flatten().to_list()

        walked = (level_pairs(CELL), level_pairs(PLANE), scope_pairs(SPACE, ""))
        return nu.List.of(*walked).iter().flatten().to_list()


def scopes(kind: type[Content[Any]], level: str) -> nu.List:
    """The ids of the scopes at ``level`` holding items of ``kind``: cells or planes. A bare read.

    Raises:
        ValueError: ``level`` is :data:`SPACE`, one scope only, or none of :data:`LEVELS`.
    """
    if level not in _SLOTS:
        msg = f"scope level {level!r} is none of {tuple(_SLOTS)}"
        raise ValueError(msg)
    return nu.list(getattr(States.contents[kind_name(kind)], _SLOTS[level]).keys())


def matched(
    kind: type[Content[Any]], scope: tuple[str, nu.StrArg], question: Mapping[str, Any]
) -> nu.Iterator:
    """The ids of the items in ``scope`` that ``kind``'s :meth:`~Content.match` holds for. A bare read.

    The one check a search and :meth:`Content.find` both make, per scope.

    Args:
        kind: The kind.
        scope: ``(level, id)``, as :meth:`Content.at` takes it.
        question: ``match``'s keywords.
    """
    held = kind.items(scope)
    return (
        nu.list(held.keys())
        .iter()
        .filter(lambda found: kind.match(kind.at(scope, nu.Str(found)), **question))
    )


def _drawn_ui(ref: StructuredRef) -> bool:
    """A ``rooted`` predicate: every chain but a bare ui one stays where it is."""
    return not isinstance(ref, UiRef)


class Drawing(ScalarQuery):
    """The term drawing one item by its address, landed under ``under``. Run it with ``nu.Eval``.

    For a program that learns which item to draw only at run time (eg a
    search hit): the kind is found by name (:func:`~nuspace.ext.content_spec`), the item reached with
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
        found = content_spec(str(kind)).kind
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
