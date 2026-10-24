"""The specs an extension registers: a :class:`Plane` ``+`` creates, a :class:`Snippet` ``/`` inserts.

Plain data. The ops that act on them, :func:`~nuspace.ops.create_plane` and
:func:`~nuspace.ops.insert_snippet`, live in :mod:`nuspace.ops`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu


__all__ = ["EMPTY", "TEXT", "Plane", "Snippet"]


#: The ``nuverse.text`` snippet: nuspace's document editing works on its cells.
#: See :class:`Snippet`.
TEXT = "nuverse.text"


@dataclass(frozen=True)
class Plane:
    """A plane ``+`` can create: data, seeded as is. No build hook.

    Everything it does lives in its cells: args, forms, lists, background
    work. Creating one only seeds it.

    Args:
        name: Registry key, and what the planes created from it record as
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
            in the order their first Plane registers; the ungrouped come
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
    children: tuple[Plane, ...] = ()
    group: str = ""
    backend: str = field(kw_only=True)

    def __post_init__(self) -> None:
        if not self.backend:
            msg = f"Plane {self.name!r}: backend is required, eg mp or async"
            raise ValueError(msg)


#: The empty plane: no cells, no children. Inherent to a space like the empty
#: cell is, so it needs no registry entry: ``""`` is no registered Plane's
#: name, and the planes made from it record ``made_by`` as none. With nothing
#: under it, it works as a folder too: grouping in the sidebar is nesting.
EMPTY = Plane(
    "",
    "Empty",
    description="An empty plane. Add cells with /, or nest planes under it.",
    meta={"editable": True, "full_width": False},
    backend="async",
)


@dataclass(frozen=True)
class Snippet:
    """Source for one cell, offered from the ``/`` menu.

    nuspace's document editing works on the cells of the ``nuverse.text``
    snippet (:data:`TEXT`), the plane's text cells, written like a document: typing on an empty line
    starts one, Enter in the title starts one at the top with the text after
    the caret, Cmd+Enter in one starts the next below, and Backspace in an
    empty one removes it. With no snippet under that name, typing opens the
    ``/`` menu and the rest is off.

    Args:
        name: The new cell's name. Installed by a package, it registers
            as ``<package>.<name>``, the registry key and what the cells made
            from it record as ``props.made_by``.
        label: What the menu shows.
        source: The cell's prog. A snippet keeps what it edits or shows in
            content items (:mod:`nuspace.content`), where search finds them.
        description: One line on what a cell made from it is for.
        ops: The ops on a cell made from it, each taking the cell id first, for whoever writes a program against its cells.
        group: The ``/`` menu heading it sits under, ``""`` for none. Groups
            show in the order their first snippet registers; the ungrouped
            come last, under no heading.
        icon: What the menu draws beside it, spelled as :class:`Plane`'s
            ``icon``. ``""`` for the default.
    """

    name: str
    label: str
    source: str
    description: str = ""
    ops: tuple[Callable[..., nu.Nu], ...] = ()
    group: str = ""
    icon: str = ""
