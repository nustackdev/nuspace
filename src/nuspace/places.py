"""Places: where a program's state is, as one value. ``nuspace.at`` and ``nuspace.here``.

A place is a scope (cell, plane, space) plus whose (this one, by key, by
id). It only builds refs, it never reads::

    nuspace.at.cell                    the running cell
    nuspace.at.cell("summary")         the cell keyed "summary"
    nuspace.at.cell(id=c)              a cell by id
    nuspace.at.plane, at.plane("team"), at.plane(id=p)
    nuspace.at.space                   the space, works everywhere

Ask a place for one of two things, then it is plain nu on refs:

- ``.state(Counter)``: its plain state, typed as ``Counter``. Reads and
  writes ``State.cells[c]`` (or ``planes[p]``, ``space``) through
  ``Counter``'s slots: ``.value.set(1)``, ``.value.fallback(0)``.
- ``.content(TextContent)``: its items of a kind, a dict by content key:
  ``["title"].value``, ``.keys()``, ``["title"].erase()``.

"This cell" is :attr:`Here.cell`, a key is the index ref
(``Space.indexes.cell_keys["summary"]``), both read at run time inside the
term, so a place bound at module level is fine. ``nuspace.here(Counter)``
is ``nuspace.at.cell.state(Counter)``, the common case.

- A key or id that finds nothing reads as NULL; a write under it raises
  (``nustd.kv.NullAddressError``).
- The bare forms read :class:`Here`, which the kernel holds around every
  cell run. Outside one (a service, the CLI, a plain script) there is no
  Here and they raise ``LookupError``. :func:`inside` binds one, for tests.
- A key read from Space under a State write works inside ``nuspace.atomic``:
  it reads Space from a snapshot.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

import nu
from nuspace.shapes.content import CELL, PLANE, SPACE, entries
from nuspace.shapes.space import Space
from nuspace.shapes.state import State
from nuspace.utils import Typed


if TYPE_CHECKING:
    import nustd.kv
    from nuspace.shapes.content import Content
    from nuspace.utils import TypedItems


__all__ = ["Here", "Place", "at", "here", "inside"]


S = TypeVar("S", bound=nu.Shape)


class Here(nu.Shape):
    """Where a cell run's body runs: the ids the kernel holds for it in a mem frame.

    The kernel opens a frame over this Shape around every cell run's body,
    so a program and its envs read ``Here.cell``, ``Here.plane``,
    ``Here.plane_run``, ``Here.cell_run``, and never set them. Read outside
    a cell run, it raises ``LookupError``: no frame is bound.
    """

    plane = nu.StrRef.slot()
    cell = nu.StrRef.slot()
    plane_run = nu.StrRef.slot()
    cell_run = nu.StrRef.slot()


def inside(
    term: nu.Nu,
    *,
    plane: nu.StrArg,
    cell: nu.StrArg = "",
    plane_run: nu.StrArg = "",
    cell_run: nu.StrArg = "",
) -> nu.Nu:
    """``term`` run as if inside a cell run: :class:`Here` bound to these ids around it.

    What the kernel does around every cell run's body, and what a test does
    to run a cell's program, so the bare places resolve::

        nuspace.places.inside(nuspace.atomic(step), plane="p1", cell="c1")
    """
    return nu.Frame(Here, term, plane=plane, cell=cell, plane_run=plane_run, cell_run=cell_run)


class Place:
    """A scope plus whose: one cell, one plane, or the space. Builds refs, never reads.

    Made by :data:`at`, never by hand. Two verbs, then it is plain nu.
    """

    __slots__ = ("_id", "_scope")

    def __init__(self, scope: str, id: nu.StrArg | None) -> None:
        self._scope = scope
        self._id = id

    def state(self, shape: type[S]) -> S:
        """The place's plain state, typed as ``shape``. A ref: ``.value.set(1)``, ``.value.fallback(0)``.

        ``nuspace.at.cell(id=c).state(Counter).value`` is
        ``Counter.value.with_parent(State.cells[c])``: it reads and writes
        ``State.cells[c].value`` as ``Counter.value`` declares it. Cost:
        O(1) to build, nothing read. Never raises.
        """
        if self._scope == CELL:
            level = State.cells[self._id]
        elif self._scope == PLANE:
            level = State.planes[self._id]
        else:
            level = State.space
        return cast("S", Typed(level, shape))

    def content(self, kind: str | type[Content[Any]]) -> TypedItems:
        """The place's items of a kind, a dict ref by content key, each typed as the kind's Shape.

        ``["title"].value.set("hey")`` writes (adds if new), ``.keys()`` lists
        the place, ``["title"].erase()`` removes one. Cost: O(1) to build,
        nothing read.

        Raises:
            LookupError: ``kind`` is not an installed kind, at build.
        """
        return entries(kind, self._scope, "" if self._id is None else self._id)

    def __repr__(self) -> str:
        whose = "" if self._id is None else f"({self._id!r})"
        return f"<place {self._scope}{whose}>"


class _This(Place):
    """A bare scope: the running cell or plane. Called with a key or an id, it names another."""

    __slots__ = ("_index",)

    def __init__(self, scope: str, here: nu.Nu, index: nustd.kv.DictRef) -> None:
        super().__init__(scope, here)
        self._index = index

    def __call__(self, key: nu.StrArg | None = None, *, id: nu.StrArg | None = None) -> Place:
        """Another cell or plane: by key (one index read at run time), or by id.

        Raises:
            TypeError: Neither or both of ``key`` and ``id``, at build.
        """
        if (key is None) == (id is None):
            msg = f"at.{self._scope}(...) takes a key or id=, exactly one"
            raise TypeError(msg)
        return Place(self._scope, self._index[key] if id is None else id)

    def __repr__(self) -> str:
        return f"<place this {self._scope}>"


class _At:
    """The entry point that makes a place: ``at.cell``, ``at.plane``, ``at.space``."""

    __slots__ = ("cell", "plane", "space")

    def __init__(self) -> None:
        self.cell = _This(CELL, Here.cell, Space.indexes.cell_keys)
        self.plane = _This(PLANE, Here.plane, Space.indexes.plane_keys)
        self.space = Place(SPACE, None)

    def __repr__(self) -> str:
        return "nuspace.at"


#: Makes a place. Bare means the running cell or plane; ``("key")`` or ``(id=...)`` another.
at = _At()


def here(shape: type[S]) -> S:
    """The running cell's own state, typed as ``shape``: ``nuspace.at.cell.state(shape)``.

    Raises:
        LookupError: Read outside a cell run, where no Here is bound.
    """
    return at.cell.state(shape)
