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


__all__ = ["EMPTY_PLANE", "TEXT_CELL", "CellSpec", "ContentSpec", "PlaneSpec"]


#: The ``nuverse.text`` Cell: nuspace's document editing works on its cells.
#: See :class:`CellSpec`.
TEXT_CELL = "nuverse.text"


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

    nuspace's document editing works on the cells of the ``nuverse.text``
    Cell (:data:`TEXT_CELL`), the plane's text cells, written like a
    document: typing on an empty line starts one, Enter in the title starts
    one at the top with the text after the caret, Cmd+Enter in one starts
    the next below, and Backspace in an empty one removes it. With no Cell
    under that name, typing opens the ``/`` menu and the rest is off.

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
    """

    name: str
    label: str
    source: str
    description: str = ""
    group: str = ""
    icon: str = ""


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
