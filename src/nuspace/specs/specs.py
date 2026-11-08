"""The specs an extension registers, one per extension point. Plain data.

- :class:`PlaneSpec`: a plane ``+`` creates.
- :class:`CellSpec`: a cell ``/`` inserts.
- :class:`ContentSpec`: a content kind cells keep items of and search finds.

The ops that act on them, :func:`~nuspace.ops.create_plane` and
:func:`~nuspace.ops.create_cell`, live in :mod:`nuspace.ops`. A content
kind's behaviors live on its class (:class:`~nuspace.content.Content`); its
spec says how a space presents it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from nuspace.content import Content


__all__ = ["EMPTY_PLANE", "CellSpec", "ContentSpec", "PlaneSpec"]


@dataclass(frozen=True)
class PlaneSpec:
    """A plane ``+`` can create: data, seeded as is. No build hook.

    Everything it does lives in its cells: args, forms, lists, background
    work. Creating one only seeds it.

    Args:
        name: Installed by a package, it registers as ``<package>.<name>``,
            the registry key and what the planes created from it record as
            ``made_by``.
        label: What the picker shows, and a new plane's default name.
        icon: A lucide icon name, ``""`` for the default. ``"lucide:<name>"``
            and ``"emoji:<char>"`` work too. A new plane's ``meta.icon``
            starts as it, unless ``meta`` sets one.
        description: One line for the picker.
        meta: What a new plane's meta starts as.
        cells: ``(name, source)`` per cell, in order.
        children: Planes seeded under it, the same shape, in order.
        group: The picker heading it sits under, ``""`` for none. Groups show
            in the order their first PlaneSpec registers; the ungrouped come
            last.
        backend: Keyword, required. The backend a plane created from it
            runs on, by registered name. Picked by the kind of work its cells
            do: many awaiting tasks run well on ``async``, sync code on ``mp``.

    Raises:
        ValueError: ``backend`` is empty.
    """

    name: str
    label: str
    icon: str = ""
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)
    cells: tuple[tuple[str, str], ...] = ()
    children: tuple[PlaneSpec, ...] = ()
    group: str = ""
    backend: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.backend:
            msg = f"PlaneSpec {self.name!r}: backend is required, eg mp or async"
            raise ValueError(msg)


#: The empty plane: no cells, no children. Inherent to a space like the empty
#: cell is, so it needs no registry entry: ``""`` is no registered plane's
#: name, and the planes made from it record ``made_by`` as none. With nothing
#: under it, it works as a folder too: grouping in the sidebar is nesting.
EMPTY_PLANE = PlaneSpec(
    "",
    "Empty",
    description="An empty plane. Add cells with /, or nest planes under it.",
    meta={"editable": True, "full_width": False},
    backend="async",
)


@dataclass(frozen=True)
class CellSpec:
    """Source for one cell, offered from the ``/`` menu.

    A cell made from it keeps the spec's classes: the protocols it promises,
    which the browser's sugar binds to, never to which spec made a cell. A
    class is a name, its promise written here. ``prose``: the cell draws
    exactly one document that registers a kit document handle (a kit
    ``MarkdownRef`` does on its own), and its value is markdown. Any spec
    whose cell keeps that promise declares it, whoever wrote it. A cell made
    from no spec, or from one no longer installed, has no classes and gets
    the plane's core behaviour only.

    One spec per class is its default, what typing on the input line
    creates: a spec claims it with ``default_for``. When two installed specs
    claim the same class, the first in registration order wins, no error.

    Args:
        name: The new cell's name. Installed by a package, it registers
            as ``<package>.<name>``, the registry key and what the cells made
            from it record as ``props.made_by``.
        label: What the menu shows.
        source: The cell's prog. A cell keeps what it edits or shows in
            content items (:mod:`nuspace.content`), where search finds them.
        description: One line on what a cell made from it is for.
        group: The ``/`` menu heading it sits under, ``""`` for none. Groups
            show in the order their first CellSpec registers; the ungrouped
            come last, under no heading.
        icon: What the menu draws beside it, spelled as :class:`PlaneSpec`'s
            ``icon``. ``""`` for the default.
        classes: The protocols its cells keep, ``("prose",)``.
        default_for: The classes it is the default of, each one of
            ``classes``.

    Raises:
        TypeError: ``classes`` or ``default_for`` is a bare string.
        ValueError: ``default_for`` names a class not in ``classes``.
    """

    name: str
    label: str
    source: str
    description: str = ""
    group: str = ""
    icon: str = ""
    classes: tuple[str, ...] = ()
    default_for: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.classes, str) or isinstance(self.default_for, str):
            msg = f"CellSpec {self.name!r}: classes and default_for are tuples, eg ('prose',)"
            raise TypeError(msg)
        stray = [c for c in self.default_for if c not in self.classes]
        if stray:
            msg = f"CellSpec {self.name!r}: default_for {stray} not among classes {self.classes}"
            raise ValueError(msg)


@dataclass(frozen=True)
class ContentSpec:
    """A content kind as a space presents it: the class, and what the search ui calls it.

    The kind's name is declared on the class alone,
    ``class TextContent(Content[Text], name="Text")``, and read here as
    :attr:`name`. Installed by a package, it registers as
    ``<package>.<name>``, ``nuverse.Text``: the name the store keys its
    items by (:func:`~nuspace.content.kind_name`).

    Args:
        kind: The :class:`~nuspace.content.Content` subclass: the schema
            and the behaviors.
        label: What the search ui calls the kind. Empty takes the class
            name, less a trailing ``Content``.
        description: One line on what an item of the kind holds.
        icon: What the search ui draws beside it, spelled as
            :class:`PlaneSpec`'s ``icon``. ``""`` for the default.

    Raises:
        TypeError: ``kind`` is no :class:`~nuspace.content.Content` subclass.
    """

    kind: type[Content[Any]]
    label: str = ""
    description: str = ""
    icon: str = ""

    def __post_init__(self) -> None:
        from nuspace.content import Content  # content imports this package

        if not (isinstance(self.kind, type) and issubclass(self.kind, Content)):
            msg = f"ContentSpec kind {self.kind!r} is no Content subclass"
            raise TypeError(msg)
        if not self.label:
            called = self.kind.__name__
            trimmed = called.endswith("Content") and called != "Content"
            object.__setattr__(self, "label", called[: -len("Content")] if trimmed else called)

    @property
    def name(self) -> str:
        """The kind's own name, as its class declares it: ``Text``."""
        return self.kind.name
