"""The specs an extension registers, one per extension point. Plain data.

- :class:`PlaneSpec`: a plane ``+`` creates, with :class:`WebOptions` when
  it shows on the web.
- :class:`CellSpec`: a cell ``/`` inserts.
- :class:`ContentSpec`: a content kind cells keep items of and search finds.
- :class:`SpecCells`: where a plane made from a spec keeps its cells' ids,
  in its own state, so its cells find each other.

The ops that make planes and cells from them, :func:`~nuspace.specs.add_plane`
and :func:`~nuspace.specs.add_cell`, are in :mod:`.ops`. A content kind's
behaviors live on its class (:class:`~nuspace.shapes.content.Content`); its
spec says how a space presents it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import nu
import nustd.kv


if TYPE_CHECKING:
    from nuspace.shapes.content import Content


__all__ = ["EMPTY_PLANE", "CellSpec", "ContentSpec", "PlaneSpec", "SpecCells", "WebOptions"]


@dataclass(frozen=True)
class WebOptions:
    """How a plane made from a spec shows on the web: the flags of its web row.

    A spec with these makes a web plane (the sidebar lists it, a tab runs
    it); one without makes a plane the web never shows.

    Args:
        editable: Its cells can be edited in the browser.
        full_width: It takes the whole width of a pane.
        compact: It draws its cells tight.
    """

    editable: bool = True
    full_width: bool = False
    compact: bool = False


class SpecCells(nu.Shape):
    """A spec plane's cells by name, in its own plane state: ``State.planes[p]``.

    Written by :func:`~nuspace.specs.add_plane` when it makes the plane, so
    a cell finds a sibling by the name the spec gave it, not by a key or a
    scan::

        nuspace.at.plane.state(SpecCells).ids["composer"]

    Two cells of one spec under one name keep the last one's id.
    """

    ids = nustd.kv.DictRef.slot(str)


@dataclass(frozen=True)
class PlaneSpec:
    """A plane ``+`` can create: data, seeded as is. No build hook.

    Everything it does lives in its cells: args, forms, lists, background
    work. Creating one only seeds it. Each cell made gets its id written in
    the plane's state, under its name (:class:`SpecCells`).

    Args:
        name: Installed by a package, it registers as ``<package>.<name>``,
            the registry key and what the planes created from it record as
            ``spec``.
        label: What the picker shows, and a new plane's default name.
        icon: A lucide icon name, ``""`` for none. ``"lucide:<name>"`` and
            ``"emoji:<char>"`` work too.
        description: One line for the picker.
        meta: What a new plane's meta starts as.
        cells: ``(name, source)`` per cell, in order.
        children: Planes seeded under it, the same shape, in order.
        group: The picker heading it sits under, ``""`` for none. Groups show
            in the order their first PlaneSpec registers; the ungrouped come
            last.
        key: A key the plane is made with, for a plane meant once per
            space. Explicit and prefixed with the package
            (``quickstart_meter``). ``""`` for none. A second plane of the
            spec then raises ``Exists``.
        web: How it shows on the web, None for a plane the web never shows.
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
    key: str = ""
    web: WebOptions | None = None
    backend: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.backend:
            msg = f"PlaneSpec {self.name!r}: backend is required, eg mp or async"
            raise ValueError(msg)


#: The empty plane: no cells, no children. Inherent to a space like the empty
#: cell is, so it needs no registry entry: ``""`` is no registered plane's
#: name, and the planes made from it record ``spec`` as none. With nothing
#: under it, it works as a folder too: grouping in the sidebar is nesting.
EMPTY_PLANE = PlaneSpec(
    "",
    "Empty",
    description="An empty plane. Add cells with /, or nest planes under it.",
    web=WebOptions(editable=True, full_width=False),
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
            from it record as ``spec``.
        label: What the menu shows.
        source: The cell's prog. A cell keeps what it edits or shows in
            content items (:mod:`nuspace.shapes.content`), where search finds them.
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
    items by (:func:`~nuspace.shapes.content.kind_name`).

    Args:
        kind: The :class:`~nuspace.shapes.content.Content` subclass: the schema
            and the behaviors.
        label: What the search ui calls the kind. Empty takes the class
            name, less a trailing ``Content``.
        description: One line on what an item of the kind holds.
        icon: What the search ui draws beside it, spelled as
            :class:`PlaneSpec`'s ``icon``. ``""`` for the default.

    Raises:
        TypeError: ``kind`` is no :class:`~nuspace.shapes.content.Content` subclass.
    """

    kind: type[Content[Any]]
    label: str = ""
    description: str = ""
    icon: str = ""

    def __post_init__(self) -> None:
        from nuspace.shapes.content import Content  # content imports this package

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
