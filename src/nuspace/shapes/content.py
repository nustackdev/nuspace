"""Content kinds: an item's Shape, how it is matched, how it draws, and finding items of a kind.

Content is the part of State with a kind (:mod:`nuspace.shapes.state`). A
kind declares the Shape of its items and behaviors over one item: ``match``
(a search's question), ``render`` and ``render_hit`` (how it draws). Adding,
reading, listing and removing items are plain nu on the refs a place builds
(``nuspace.at.cell.content(TextContent)["title"]``), so a kind has no
accessors of its own. :func:`entries` is the one spelling of where a kind's
items sit at a place, which places and the finding below build on.

Finding reads one kind's subtree, scope by scope, all bare reads:
:func:`scopes` lists the cells or planes holding its items, :func:`matched`
the items ``match`` holds for in one scope, :meth:`Content.find` both
together. A search reads per kind, so it never touches another kind's
items; the web device's search drives it a place at a time
(:mod:`nuspace.devices.web.search`).

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar, cast, get_args, get_origin

import nu
from nu.engine import Declared
from nu.lang import ScalarQuery
from nu.lang.sentinels import UNSET, Unset
from nuspace.specs.registry import content_spec, kind_name
from nuspace.utils import TypedItems
from nustd.ui.core import Ref as UiRef

from .state import State


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

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
    "address",
    "entries",
    "kind_name",
    "matched",
    "scopes",
]


S = TypeVar("S", bound=nu.Shape)


#: A scope: one cell's items.
CELL = "cell"

#: A plane's own items.
PLANE = "plane"

#: The space's own items. Its scope id is ``""``.
SPACE = "space"

#: Every scope level, narrowest first: the order a search walks them in.
LEVELS = (CELL, PLANE, SPACE)

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


def _name(kind: str | type[Content[Any]]) -> str:
    """A kind's registered name, ``<package>.<name>``, or the name given as is."""
    return kind if isinstance(kind, str) else kind_name(kind)


def _schema(kind: str | type[Content[Any]]) -> type[nu.Shape]:
    """A kind's item Shape, the kind found by its registered name when given one."""
    found = content_spec(kind).kind if isinstance(kind, str) else kind
    return found.schema()


def _place(level: str, scope_id: nu.StrArg) -> tuple[str, nu.StrArg]:
    """``(level, scope_id)`` checked: the level one of :data:`LEVELS`.

    Raises:
        ValueError: The level is none of :data:`LEVELS`.
    """
    if level not in LEVELS:
        msg = f"scope level {level!r} is none of {LEVELS}"
        raise ValueError(msg)
    return level, scope_id


def entries(
    kind: str | type[Content[Any]],
    level: str,
    scope_id: nu.StrArg = "",
    *,
    schema: type[nu.Shape] | None = None,
) -> TypedItems:
    """One place's items of a kind, by content key, each typed as the kind's Shape.

    ``[key].body`` is ``Note.body.with_parent(...entries[key])``, the kind's
    slot placed under the item. The mapping is the store's own: ``keys()`` lists
    the place, ``[key].erase()`` removes one, and a write to a new key adds
    it. A place no item ever landed in has no mapping yet: ``exists()`` is
    False, and ``keys`` or ``len`` raise. Builds a ref, reads nothing.

    Paths, by level::

        CELL   State.content_cells[kind].cells[scope_id].entries
        PLANE  State.content_planes[kind].planes[scope_id].entries
        SPACE  State.content_space[kind].entries

    Args:
        kind: The kind, or its registered name (``nuverse.Text``).
        level: :data:`CELL`, :data:`PLANE` or :data:`SPACE`. A python str,
            so the path is known when the ref is built.
        scope_id: The cell or plane id, any ``StrArg``. Ignored for the space.
        schema: The item Shape, when ``kind`` is a name with no installed
            kind behind it. Defaults to the kind's own.

    Raises:
        ValueError: The level is none of :data:`LEVELS`.
        LookupError: ``kind`` is not installed and no ``schema`` is given.
    """
    level, scope_id = _place(level, scope_id)
    name = _name(kind)
    if level == CELL:
        held = State.content_cells[name].cells[scope_id].entries
    elif level == PLANE:
        held = State.content_planes[name].planes[scope_id].entries
    else:
        held = State.content_space[name].entries
    # Each item is the empty Entry: the kind's Shape sits on it through with_parent.
    return TypedItems(held, schema if schema is not None else _schema(kind))


def address(
    kind: str | type[Content[Any]], scope: tuple[str, nu.StrArg], key: nu.StrArg
) -> nu.Dict:
    """An item's address as plain data: ``{"kind": name, "scope": [level, id], "key": key}``.

    What a search hit, :meth:`Content.find` and a cell linking to an item
    keep. Read it back with :func:`entries`.

    Args:
        kind: The kind, or its registered name.
        scope: ``(level, id)``, ``id`` ``""`` for the space.
        key: The item's content key at that place.
    """
    level, scope_id = scope
    return nu.Dict.of(kind=_name(kind), scope=nu.List.of(level, scope_id), key=key)


class Content(Generic[S]):
    """A kind: the behaviors of one kind of item and the Shape they read. Not a Shape.

    Subclass it over the item Shape,
    ``class TextContent(Content[Text], name="Text")``, and register it in an
    extension with a ``ContentSpec``, which says how a space presents it.
    Every behavior is a classmethod; a kind is never instantiated.

    Behaviors:

    - :meth:`match`, the question, as keyword arguments. The item's own
      logic: it works anywhere. A keyword left out stays ``UNSET``, so
      ``match`` branches on it at construction and the term it builds holds
      only the checks asked for.
    - :meth:`render`, :meth:`render_hit`: how an item draws in full and as a
      search hit. Bare ui chains, landed under wherever the drawing goes
      (:class:`Drawing`).
    - :meth:`form`: the search form, generated from ``match``'s keywords.
    - :meth:`find`: every item ``match`` holds for, from every place.

    Every kind names itself: its identity in the store, so one word, no
    dots, by convention the class name less ``Content``. Installed, its
    package goes in front (:func:`kind_name`).

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

    @classmethod
    def find(cls, **question: Any) -> nu.Nu:  # noqa: ANN401
        """Every item of the kind :meth:`match` holds for, from every place. A bare read.

        Cells first, then planes, then the space's, as a search walks them.
        The keywords are :meth:`match`'s; one left out stays ``UNSET``, so
        asked nothing, every item ``match`` lets through is found. Its
        caller brackets it, eg ``nuspace.atomic(...)``.

        Yields:
            A list of ``(address, item)`` pairs: the item's :func:`address`
            and its fields, plain data.
        """
        name = kind_name(cls)

        def scope_pairs(level: str, scope_id: nu.StrArg) -> nu.Nu:
            scope = (level, scope_id)
            held = entries(cls, level, scope_id)

            def pair(found: nu.Attr) -> nu.Nu:
                key = nu.Str(found)
                return nu.Tuple.of(address(name, scope, key), held[key].extract())

            return matched(cls, scope, question).map(pair).to_list()

        def level_pairs(level: str) -> nu.Nu:
            each = scopes(cls, level).iter().map(lambda at: scope_pairs(level, nu.Str(at)))
            return each.flatten().to_list()

        walked = (level_pairs(CELL), level_pairs(PLANE), scope_pairs(SPACE, ""))
        return nu.List.of(*walked).iter().flatten().to_list()


# --- Finding -----------------------------------------------------------------------


def _keys(held: nu.Nu) -> nu.List:
    """A mapping's keys, ``[]`` when it was never written.

    A kind's level, or one place of it, exists only once an item landed
    there: a kind never written at a plane has no ``planes`` to list.
    """
    return nu.list(nu.If(held.exists(), nu.list(held.keys()), []))


def scopes(kind: type[Content[Any]], level: str) -> nu.List:
    """The ids of the cells or planes holding items of ``kind``. A bare read, one kind's index.

    Raises:
        ValueError: ``level`` is :data:`SPACE` (one place only) or none of :data:`LEVELS`.
    """
    name = kind_name(kind)
    if level == CELL:
        return _keys(State.content_cells[name].cells)
    if level == PLANE:
        return _keys(State.content_planes[name].planes)
    msg = f"scope level {level!r} is none of {(CELL, PLANE)}"
    raise ValueError(msg)


def matched(
    kind: type[Content[Any]], scope: tuple[str, nu.StrArg], question: Mapping[str, Any]
) -> nu.Iterator:
    """The keys of the items at ``scope`` that ``kind``'s :meth:`~Content.match` holds for. A bare read.

    Args:
        kind: The kind.
        scope: ``(level, id)``, ``id`` ``""`` for the space.
        question: ``match``'s keywords.
    """
    held = entries(kind, *scope)
    return _keys(held).iter().filter(lambda found: kind.match(held[nu.Str(found)], **question))


# --- Drawing -----------------------------------------------------------------------


def _drawn_ui(ref: StructuredRef) -> bool:
    """A ``rooted`` predicate: every chain but a bare ui one stays where it is."""
    return not isinstance(ref, UiRef)


class Drawing(ScalarQuery):
    """The term drawing one item by its address, landed under ``under``. Run it with ``nu.Eval``.

    For a program that learns which item to draw only at run time (eg a
    search hit): the kind is found by name (``content_spec``), the item
    reached through :func:`entries`, and its :meth:`~Content.render` (or
    :meth:`~Content.render_hit`) term built, its bare ui chains spliced
    under ``under``. ``under`` is a ref the program names bare like any of
    its ui refs: it sits in a structural slot, never read, so the program's
    own rewrites land it first and the drawing lands where it does.

    Args:
        kind: The kind's registered name.
        level: The scope's level, one of :data:`LEVELS`.
        scope: The cell or plane id, ``""`` for the space.
        key: The item's content key.
        under: A ui ref the drawing lands under.
        hit: Draw ``render_hit`` rather than ``render``.

    Yields:
        The drawing, a term: ``nu.Eval(Drawing(...))`` draws it. It reads the
        item bare, so its caller brackets it, as any read:
        ``nuspace.atomic(nu.Eval(Drawing(...)))``.
    """

    _structural = Declared(value=frozenset({4}), name="structural")

    def __init__(
        self,
        kind: nu.StrArg,
        level: nu.StrArg,
        scope: nu.StrArg,
        key: nu.StrArg,
        under: nu.Nu,
        *,
        hit: bool = False,
    ) -> None:
        super().__init__(kind, level, scope, key, under)
        self._payload["hit"] = hit

    def _term(self, kind: object, level: object, scope: object, key: object) -> nu.Nu:
        found = content_spec(str(kind)).kind
        item = entries(found, str(level), str(scope))[str(key)]
        drawn = found.render_hit(item) if self._payload["hit"] else found.render(item)
        return nu.shape.reroot(drawn, self._children[4], rooted=_drawn_ui)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, level, scope, key = children[:4]

        def thunk(rt: Runtime) -> object:
            return self._term(kind(rt), level(rt), scope(rt), key(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, level, scope, key = children[:4]

        async def athunk(rt: Runtime) -> object:
            return self._term(await kind(rt), await level(rt), await scope(rt), await key(rt))

        return athunk
