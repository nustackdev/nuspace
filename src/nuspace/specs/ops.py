"""Making planes and cells from specs: ``nuspace.specs.add_plane`` and ``add_cell``.

``add_cell`` is a core op made from a spec: a bare term, the caller
brackets it. ``add_plane`` is a wrapper, not a core op: it writes more than
one store, so it brackets each step itself and runs them in a row, one
commit each:

0. Before any bracket: every id minted, then every cell's fabrics worked
   out (:class:`~nuspace.ops.interactions.Fabrics` builds each prog), so
   no build runs inside a commit and a retried commit builds nothing.

1. Space: the plane, its cells, its children and theirs, the whole tree in
   one commit.
2. State: each plane's cells by name, in that plane's state
   (:class:`~nuspace.specs.specs.SpecCells`), so siblings find each other.
3. Web, when the spec has ``web=``: the plane's web row.

A retried commit writes the same ids, and the later steps name what the
first one made.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.kv
from nuspace.ops import cell, plane
from nuspace.ops.interactions import Fabrics
from nuspace.shapes.plane import ROOT
from nuspace.shapes.state import State
from nuspace.utils import MintId

from .registry import cell_spec, plane_spec, registered_name, short_name
from .specs import SpecCells


if TYPE_CHECKING:
    from .specs import CellSpec, PlaneSpec


__all__ = ["add_cell", "add_plane"]


class _Minted(nu.Shape):
    """What the spec ops work out before any bracket, under names fixed at build.

    ``ids``: the minted ids. ``fabrics``: each cell's fabrics.
    """

    ids = nu.DictRef.slot(str)
    fabrics = nu.DictRef.slot(list)


def _icon(icon: str) -> str:
    """A spec's icon as a plane stores it: a bare name is a lucide one."""
    if not icon or ":" in icon:
        return icon
    return f"lucide:{icon}"


class _Tree:
    """One spec tree laid out at build: the mints, the analyses, the writes per store."""

    def __init__(self) -> None:
        self.mints: list[nu.Nu] = []
        self.analyses: list[nu.Nu] = []
        self.space: list[nu.Nu] = []
        self.state: list[nu.Nu] = []
        self.web: list[nu.Nu] = []

    def minted(self, prefix: str, given: nu.StrArg | None = None) -> nu.Str:
        """A fresh slot holding ``given``, or an id minted under ``prefix``."""
        slot = _Minted.ids[f"{prefix}{len(self.mints)}"]
        self.mints.append(slot.set(MintId(prefix) if given is None else given))
        return nu.Str(slot)

    def analysed(self, source: str, pid: nu.Str, cid: nu.Str) -> nu.Nu:
        """A fresh slot holding the fabrics ``source`` uses as cell ``cid`` on ``pid``."""
        slot = _Minted.fabrics[f"f{len(self.analyses)}"]
        self.analyses.append(slot.set(Fabrics(source, pid, cid)))
        return slot

    def lay(
        self,
        spec: PlaneSpec,
        pid: nu.Str,
        *,
        parent: nu.StrArg,
        name: nu.StrArg,
        before: nu.StrArg | None = None,
        after: nu.StrArg | None = None,
    ) -> None:
        """``spec``'s plane at ``pid``, its cells, then its children, each under its own minted id."""
        self.space.append(
            plane.add(
                pid,
                parent=parent,
                before=before,
                after=after,
                name=name,
                key=spec.key,
                icon=_icon(spec.icon),
                backend=spec.backend,
                spec=registered_name(spec),
                meta=dict(spec.meta),
            )
        )
        named = SpecCells.ids.with_parent(State.planes[pid]) if spec.cells else None
        for cell_name, source in spec.cells:
            cid = self.minted("c")
            fabrics = self.analysed(source, pid, cid)
            self.space.append(cell.add(pid, source, id=cid, name=cell_name, fabrics=fabrics))
            self.state.append(named.set_item(cell_name, cid))  # type: ignore[union-attr]
        if spec.web is not None:
            self.web.append(_web_row(pid, spec))
        for child in spec.children:
            self.lay(child, self.minted("p"), parent=pid, name=child.label)


def _web_row(pid: nu.Str, spec: PlaneSpec) -> nu.Nu:
    """The plane's web row, from ``spec.web``: ``nuspace.web.add``, the plane shows on the web.

    Imported here, not at the top, so core loads without the web device.
    """
    from nuspace.web import ops as web

    flags = spec.web
    return web.add(
        pid,
        editable=flags.editable,  # type: ignore[union-attr]
        width=flags.width,  # type: ignore[union-attr]
    )


def add_plane(
    spec: PlaneSpec | str,
    id: nu.StrArg | None = None,
    *,
    parent: nu.StrArg = ROOT,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Make a plane from a spec: the plane, its cells in order, its children under it.

    A wrapper that brackets itself, run it on its own: first every id and
    every cell's fabrics, outside any bracket, then up to three commits in
    a row, Space (the whole tree), then State (each plane's cells by
    name, :class:`~nuspace.specs.specs.SpecCells`), then the web row when
    the spec has ``web=``. A failure in the first leaves nothing; one in a
    later step leaves the tree without its state or web row. Each plane
    records the spec it was made from (``spec``, and
    ``Space.indexes.spec_planes``), and takes the spec's key when it has one.
    Cost: O(spec size).

    Args:
        spec: The spec, or its registered name (``nudemos.movies``).
        id: The top plane's id. Minted when absent; children always mint.
        parent: The plane it hangs under.
        before: A sibling to place it before.
        after: A sibling to place it after. Neither: the end.
        name: What to call it. ``spec.label`` when absent.
        into: A ref set to the top plane's id, once the Space commit landed.

    Raises:
        Missing: No spec of that name (at build), no parent or anchor.
        Removed: The parent or the anchor is removed.
        Exists: The id or the spec's key is taken.
        Refused: An anchor that is not a sibling, a reserved id.
    """
    found = plane_spec(spec) if isinstance(spec, str) else spec
    tree = _Tree()
    top = tree.minted("p", id)
    tree.lay(
        found,
        top,
        parent=parent,
        name=found.label if name is None else name,
        before=before,
        after=after,
    )
    # Mints first: an analysis is offered its cell's and plane's ids.
    steps = [*tree.mints, *tree.analyses, nustd.kv.atomic(nu.Sequential(*tree.space))]
    if into is not None:
        # A kv ref (a device's Conn row) is its own commit; atomic passes a mem ref through.
        steps.append(nustd.kv.atomic(into.set(top)))
    if tree.state:
        steps.append(nustd.kv.atomic(nu.Sequential(*tree.state)))
    if tree.web:
        steps.append(nustd.kv.atomic(nu.Sequential(*tree.web)))
    return nu.Frame(_Minted, nu.Sequential(*steps), ids=nu.Dict.of(), fabrics=nu.Dict.of())


def add_cell(
    plane: nu.StrArg,
    spec: CellSpec | str,
    *,
    id: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    fabrics: list[str] | nu.Nu | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Add a cell from a spec: its source as the prog, its short name as the name.

    :func:`nuspace.cell.add` with the spec's fields: the cell records the
    name the spec registers under (``nuverse.slider``) as ``spec``, and in
    ``Space.indexes.spec_cells``. A bare op: the caller brackets it. Cost:
    O(1), about 20 keys.

    Its first step mints the id and works out the fabrics, then
    :func:`nuspace.cell.add` takes them. That step reads no store key, so
    ``bracketed`` puts no bracket on it and under ``atomic`` it runs before
    the commit opens. A retried ``atomic`` repeats it; a caller that
    retries or brackets more than this op passes ``fabrics=`` instead.

    Args:
        plane: The plane it goes on.
        spec: The spec, or its registered name.
        id: Its id. Minted when absent.
        before: A cell of the plane to place it before.
        after: A cell of the plane to place it after. Neither: the end.
        fabrics: The fabrics the spec's source uses, worked out already
            (see :func:`nuspace.cell.add`). Absent: worked out first.
        into: A ref set to the id in the same commit.

    Raises:
        Missing: No spec of that name (at build), no plane or anchor.
        Removed: The plane or the anchor is removed.
        Exists: The id is taken.
        Refused: An anchor on another plane.
    """
    found = cell_spec(spec) if isinstance(spec, str) else spec
    minted = _Minted.ids["c"]
    cid = nu.Str(minted)
    first: list[nu.Nu] = [minted.set(MintId("c") if id is None else id)]
    if fabrics is None:
        fabrics = _Minted.fabrics["c"]
        first.append(fabrics.set(Fabrics(found.source, plane, cid)))
    made = cell.add(
        plane,
        found.source,
        id=cid,
        before=before,
        after=after,
        name=short_name(found.name),
        spec=registered_name(found),
        fabrics=fabrics,
        into=into,
    )
    return nu.Frame(_Minted, nu.Sequential(*first, made), ids=nu.Dict.of(), fabrics=nu.Dict.of())
