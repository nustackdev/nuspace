"""``nuspace.cell``: the ops over ``Space.cells``. A cell is a program on one plane.

A cell's row names its ``plane``; the plane lists it in ``cells``. Both
sides change in one commit. Two versions move: ``Cell.version`` only with
the prog (what reload compares a cell run's version to), ``Plane.version``
with any write to any of the plane's cells (the one key to watch for a
plane's cells).

Every op is a bare term the caller brackets (see :mod:`nuspace.ops`).
Programs write the module in front: ``nuspace.cell.add(...)``.
"""

from __future__ import annotations

from typing import Any

import nu
import nustd.time
from nuspace.errors import Exists, Missing
from nuspace.shapes.space import Space
from nuspace.utils import MintId, Require, anchor_of, place
from nuspace.utils.checks import (
    anchored,
    key_free,
    key_spelled,
    live,
    refuse,
    text,
    unkey,
    when,
)

from .interactions import Fabrics


__all__ = [
    "add",
    "exists",
    "move",
    "remove",
    "remove_key",
    "rename",
    "set_key",
    "set_meta",
    "set_prog",
    "title",
]


def _bump(plane: nu.StrArg) -> nu.Nu:
    """Count a write to one of the plane's cells on ``Plane.version``."""
    version = Space.planes[plane].version
    return version.set(version.fallback(0) + 1)


def _edited(id: nu.StrArg) -> nu.Nu:
    """Stamp ``modified_at`` and count the write on the cell's plane."""
    row = Space.cells[id]
    return row.modified_at.set(nustd.time.time()) >> _bump(row.plane)


def add(
    plane: nu.StrArg,
    prog: nu.StrArg,
    *,
    id: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
    name: nu.StrArg = "",
    key: nu.StrArg = "",
    spec: nu.StrArg = "",
    meta: dict[str, Any] | nu.Nu | None = None,
    fabrics: list[str] | nu.Nu | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Create a cell on a plane. Create only: an id taken raises. Does not run it.

    One commit: the row (name, key, prog, the fabrics worked out from the
    prog, version 1, plane, spec, meta, created_at), the id in the plane's
    ``cells`` (before or after a sibling, else at the end), the key in
    ``Space.indexes.cell_keys``, the id in ``spec_cells[spec].ids`` when
    given, and ``Plane.version`` +1. A plane run picks the cell up, or
    reload does for a live one. Cost: O(1), about 20 keys.

    Working out the fabrics builds the prog in this process (its module
    code runs), before any store key is read. A caller that brackets more
    than this op, or retries it, works them out first in its own step
    outside the bracket and passes ``fabrics=``, so no build runs inside a
    commit: ``nuspace.specs.add_plane``, reactions and the web device do.

    Args:
        plane: The plane it goes on.
        prog: Its source.
        id: Its id. Minted when the op evaluates when absent.
        before: A cell of the plane to place it before.
        after: A cell of the plane to place it after. Neither: the end.
        name: Display text only.
        key: An optional handle in key chars (letters, digits, ``_``, ``-``),
            case-sensitive, ``""`` for none.
        spec: The spec it was made from, ``""`` for none.
        meta: The free dict, for programs. nuspace never reads it.
        fabrics: The fabrics the prog uses, worked out already, eg a ref
            set from :class:`~nuspace.ops.interactions.Fabrics` with the
            same prog, plane and id. Stored as given. Absent: worked out
            here.
        into: A ref set to the id in the same commit, for a minted one.

    Raises:
        Exists: The id or the key is taken.
        Missing: No plane or anchor with that id.
        Removed: The plane or the anchor is removed.
        Refused: An anchor on another plane, a key that is not key chars
            (a literal at build).
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    spelled = key_spelled(key, "cell", empty_ok=True)

    def write(cid: nu.StrArg, used: list[str] | nu.Nu) -> nu.Nu:
        rows = Space.cells
        row = rows[cid]
        listed = Space.planes[plane].cells

        def made(now: nu.ObjectRef) -> nu.Nu:
            return (
                row.name.set(name)
                >> row.key.set(key)
                >> row.prog.set(prog)
                >> row.fabrics.set(used)
                >> row.version.set(1)
                >> row.plane.set(plane)
                >> row.spec.set(spec)
                >> row.meta.set(nu.Dict.create() if meta is None else meta)
                >> row.created_at.set(now)
                >> row.modified_at.set(now)
            )

        writes = (
            refuse(rows.contains(cid), Exists, "cell ", cid, " exists")
            >> live(Space.planes, plane, "plane")
            >> anchored(listed, rows, anchor, cid, "cell", text("plane ", plane))
            >> spelled
            >> key_free(Space.indexes.cell_keys, key, None, "cell")
            >> nu.let(nustd.time.time(), made)
            >> place(listed, cid, before=before, after=after)
            >> when(key, Space.indexes.cell_keys.set_item(key, cid))
            >> when(spec, Space.indexes.spec_cells[spec].ids.set_item(cid, True))
            >> _bump(plane)
        )
        return writes if into is None else writes >> into.set(cid)

    def analysed(cid: nu.StrArg) -> nu.Nu:
        if fabrics is not None:
            return write(cid, fabrics)
        return nu.let(Fabrics(prog, plane, cid), lambda found: write(cid, found))

    if id is None:
        return nu.let(MintId("c"), lambda cid: analysed(nu.Str(cid)))
    return analysed(id)


def remove(id: nu.StrArg) -> nu.Nu:
    """Remove a cell softly: stamped, kept and readable, with its runs, state and content.

    Stamps ``removed_at`` and ``removed_by=id``, takes the id out of its
    plane's ``cells``, drops its key from ``cell_keys`` (the row keeps
    ``.key``), adds the id to ``Space.indexes.removed``, ``Plane.version``
    +1. Writes nothing about runs: the kernel sees the removed cell and
    interrupts its live cell runs. Cost: O(1), about 7 keys.

    Raises:
        Missing: No cell with that id.
        Removed: It is removed already.
    """
    row = Space.cells[id]
    return (
        live(Space.cells, id, "cell")
        >> Space.planes[row.plane].cells.del_item(id)
        >> unkey(Space.indexes.cell_keys, row.key, id)
        >> row.removed_at.set(nustd.time.time())
        >> row.removed_by.set(id)
        >> Space.indexes.removed.set_item(id, True)
        >> _bump(row.plane)
    )


def move(
    id: nu.StrArg,
    *,
    plane: nu.StrArg | None = None,
    before: nu.StrArg | None = None,
    after: nu.StrArg | None = None,
) -> nu.Nu:
    """Move a cell before or after a sibling, or to the end; with ``plane``, onto another plane.

    Out of the old plane's ``cells``, into the target's, ``Cell.plane`` set,
    ``Plane.version`` +1 on both. Left out, ``plane`` is the cell's own. The
    kernel interrupts its live runs on the old plane; reload gives it a
    first run in the new plane's live runs. Cost: O(1), about 10 keys.

    Raises:
        Missing: No cell, target plane or anchor with that id.
        Removed: The cell, the target plane or the anchor is removed.
        Refused: An anchor not on the target plane, or the cell itself.
        TypeError: Both ``before`` and ``after``, at build.
    """
    anchor = anchor_of(before, after)
    row = Space.cells[id]
    target = row.plane if plane is None else plane
    listed = Space.planes[target].cells
    checks = live(Space.cells, id, "cell")
    if plane is not None:
        checks = checks >> live(Space.planes, plane, "plane")
    # The old plane is read off the row, so everything about it comes before the row moves.
    moved = (
        Space.planes[row.plane].cells.del_item(id)
        >> _bump(row.plane)
        >> place(listed, id, before=before, after=after)
        >> row.plane.set(target)
        >> row.modified_at.set(nustd.time.time())
    )
    if plane is not None:
        moved = moved >> _bump(plane)
    return (
        checks >> anchored(listed, Space.cells, anchor, id, "cell", text("plane ", target)) >> moved
    )


def rename(id: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Set a cell's name, display text only. ``Cell.version`` stays. Cost: O(1), 3 keys.

    Raises:
        Missing: No cell with that id.
        Removed: It is removed.
    """
    return live(Space.cells, id, "cell") >> Space.cells[id].name.set(name) >> _edited(id)


def set_key(id: nu.StrArg, key: nu.StrArg) -> nu.Nu:
    """Set a cell's key, or change it: the old entry out of ``cell_keys``, the new one in.

    Cost: O(1), about 6 keys.

    Raises:
        Missing: No cell with that id.
        Removed: It is removed.
        Exists: Another cell holds the key.
        Refused: An empty key, or one not in key chars. A literal at build.
    """
    spelled = key_spelled(key, "cell", empty_ok=False)
    index = Space.indexes.cell_keys
    row = Space.cells[id]
    old = row.key.fallback("")
    return (
        spelled
        >> live(Space.cells, id, "cell")
        >> key_free(index, key, id, "cell")
        >> nu.IfDo((old != "").and_(old != key), index.del_item(old))
        >> index.set_item(key, id)
        >> row.key.set(key)
        >> _edited(id)
    )


def remove_key(id: nu.StrArg) -> nu.Nu:
    """Drop a cell's key: out of ``cell_keys``, ``.key`` cleared, free for other cells.

    Cost: O(1), 4 keys.

    Raises:
        Missing: No cell with that id, or it has no key.
        Removed: It is removed.
    """
    row = Space.cells[id]
    return (
        live(Space.cells, id, "cell")
        >> refuse(row.key.fallback("") == "", Missing, "cell ", id, " has no key")
        >> Space.indexes.cell_keys.del_item(row.key)
        >> row.key.set("")
        >> _edited(id)
    )


def set_prog(id: nu.StrArg, prog: nu.StrArg, *, fabrics: list[str] | nu.Nu | None = None) -> nu.Nu:
    """Replace a cell's program. Live runs keep the old one; reload reruns the cell.

    One commit: prog, fabrics (worked out from the prog, which builds it in
    this process), ``Cell.version`` +1, ``modified_at``, ``Plane.version``
    +1. Nothing validates: a prog that does not build stores fine and uses
    no fabric. Cost: O(1), 5 keys.

    Worked out here, the build runs after the row is read, so inside the
    caller's commit. A caller that brackets it works the fabrics out first,
    in its own step outside the bracket, and passes ``fabrics=``, as the
    web device does.

    Args:
        id: The cell.
        prog: Its new source.
        fabrics: The fabrics the new prog uses, worked out already (see
            :func:`add`). Stored as given. Absent: worked out here.

    Raises:
        Missing: No cell with that id.
        Removed: It is removed.
    """
    row = Space.cells[id]

    def written(used: list[str] | nu.Nu) -> nu.Nu:
        return (
            row.prog.set(prog)
            >> row.fabrics.set(used)
            >> row.version.set(row.version.fallback(0) + 1)
            >> _edited(id)
        )

    checked = live(Space.cells, id, "cell")
    if fabrics is not None:
        return checked >> written(fabrics)
    return checked >> nu.let(Fabrics(prog, row.plane, id), written)


def set_meta(id: nu.StrArg, fields: dict[str, Any] | nu.Nu) -> nu.Nu:
    """Merge ``fields`` into a cell's free meta dict, shallow. ``Cell.version`` stays.

    Cost: O(fields).

    Raises:
        Missing: No cell with that id.
        Removed: It is removed.
    """
    return live(Space.cells, id, "cell") >> Space.cells[id].meta.update(fields) >> _edited(id)


def exists(id: nu.StrArg, *, removed: bool = False) -> nu.Bool:
    """Whether a cell with this id is in the space: a row, not removed. A read, never raises.

    A plane removal stamps its cells too, so one row says it. ``removed=True``
    counts removed rows as well. Cost: O(1), 2 point reads.
    """
    there = Space.cells.contains(id)
    return there if removed else there.and_(Space.cells[id].removed_at.exists().not_())


def title(id: nu.StrArg) -> nu.Str:
    """What a list or a header shows for a cell: its name, else its id. Cost: O(1), 2 reads.

    Raises:
        Missing: No cell with that id.
    """
    name = Space.cells[id].name.fallback("")
    shown = nu.If(name == "", id, name)
    return nu.Str(Require(Space.cells.contains(id), shown, text("no cell ", id), exc_cls=Missing))
