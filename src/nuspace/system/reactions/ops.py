"""``nuspace.system.reactions``: reactions, each a cell on the reactions plane that runs a plane.

A reaction is known by its id, its cell's id. Its plane is kept twice, in
State: in its own cell state (:class:`~.shapes.Reaction`) and in the
plane's :attr:`~.shapes.Registry.by_plane`, so remove and clear are point
reads and nothing walks the reaction cells.

Each op writes both stores, Space (the cell) and State (where it is kept),
so it is a wrapper, not a core op: it brackets its own steps and runs them
in a row, one commit each, in an order that a crash in between leaves
harmless (a ``by_plane`` entry naming no live reaction, which :func:`clear`
drops). Call it bare, never inside ``nuspace.atomic``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
from nuspace import ops
from nuspace.errors import Missing
from nuspace.ops.brackets import atomic
from nuspace.places import at
from nuspace.shapes import Space
from nuspace.utils import MintId, keys_of
from nuspace.utils.checks import live, refuse

from .shapes import PLANE, Reaction, registry


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = ["add", "clear", "remove", "source"]


_HEAD = """\
import nu
import nustd.kv
import nuspace
from nuspace import Space, State
from nuspace.system.reactions import react
"""


def _imports(imports: Sequence[str] | str) -> str:
    """Import lines as source, one per line."""
    lines = [imports] if isinstance(imports, str) else list(imports)
    return "".join(line.rstrip("\n") + "\n" for line in lines if line)


def source(
    change: nu.StrArg,
    plane: nu.StrArg,
    reaction: nu.StrArg,
    *,
    imports: Sequence[str] | str = (),
) -> nu.Str:
    """A reaction cell's prog: ``react(change, PLANE, REACTION)``. A str term.

    The composition lives in :func:`~.plane.react`, so stored progs name one
    public entry and stay valid when the code behind it moves. ``nu``,
    ``nustd``, ``nuspace``, ``Space`` and ``State`` are in scope for
    ``change``; ``imports`` adds more.

    Args:
        change: Source of an expression yielding a subscription, eg
            ``'nuspace.at.plane(id="chat").state(Inbox).messages.on_change()'``.
        plane: The plane it runs.
        reaction: The reaction's id, what its runs are recorded ``by``.
        imports: Import lines put after the standard ones.
    """
    head = _HEAD + _imports(imports)
    return (
        nu.Str(head + "\n#: The plane this reaction runs.\nPLANE = ")
        + nu.Repr(plane)
        + nu.Str("\n#: This reaction's id, what its runs are recorded by.\nREACTION = ")
        + nu.Repr(reaction)
        + nu.Str("\n\n\ndef out():\n    return react(\n        ")
        + nu.Str(change)
        + nu.Str(",\n        PLANE,\n        REACTION,\n    )\n")
    )


def add(
    change: nu.StrArg,
    plane: nu.StrArg,
    *,
    imports: Sequence[str] | str = (),
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Run ``plane`` on every notification of ``change``: a new reaction cell. Additive.

    Adding the same change and plane twice gives two reactions. A caller
    that wants one keeps the id in its own state and adds only when it has
    none. The plane runs to completion (see :mod:`.plane`).

    In a row: the id minted and the source loaded, as the kernel will load
    it, before anything is written; then State, one commit: the target
    plane checked, the plane in the reaction's own cell state and the id in
    ``by_plane[plane]``; then Space, one commit: the cell, at the end of the
    reactions plane; then ``into``. The live run of the reactions plane
    gives it a first run (reload). Cost: O(1), about 25 keys.

    Args:
        change: Source of an expression yielding a subscription. See
            :func:`source` for what is in scope.
        plane: The plane to run.
        imports: Import lines for names ``change`` uses, eg
            ``("from myapp.shapes import Inbox",)``.
        into: A ref set to the reaction's id.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        nu.prog.ConstructionError: The source does not load (a bad change, a
            bad import). Nothing is written.
    """

    def made(minted: nu.ObjectRef) -> nu.Nu:
        reaction = nu.Str(minted)
        src = source(change, plane, reaction, imports=imports)
        kept = (
            live(Space.planes, plane, "plane")
            >> at.cell(id=reaction).state(Reaction).plane.set(plane)
            >> registry().by_plane[plane].ids.set_item(reaction, True)
        )
        cell = ops.cell.add(PLANE, src, id=reaction, name=plane, fabrics=[])
        steps = atomic(kept) >> atomic(cell)
        if into is not None:
            steps = steps >> atomic(into.set(reaction))
        # Loaded first and held only for that: source that does not load
        # raises here, before anything is written.
        return nu.let(nu.prog.LoadNu(src), lambda _: steps)

    return nu.let(MintId("c"), made)


def _known(reaction: nu.StrArg) -> nu.Bool:
    """Whether ``reaction`` is a live reaction: a cell on the reactions plane, not removed, with its plane kept."""
    row = Space.cells[reaction]
    on = row.plane.fallback("") == PLANE
    kept = at.cell(id=reaction).state(Reaction).plane.exists()
    return on.and_(row.removed_at.exists().not_()).and_(kept)


def remove(reaction: nu.StrArg) -> nu.Nu:
    """Remove a reaction: its cell (the kernel interrupts its run), then its ``by_plane`` entry.

    Two commits in a row: Space, the reaction checked and its cell removed;
    then State, its id out of ``by_plane`` of the plane its own cell state
    names. A run of the plane it already asked for is left to finish.
    Cost: O(1), about 10 keys.

    Raises:
        Missing: No such reaction: no cell, one removed already, or one that
            is not a reaction (the park cell).
    """
    mine = at.cell(id=reaction).state(Reaction).plane
    checked = refuse(_known(reaction).not_(), Missing, "no reaction ", reaction)
    dropped = nu.IfDo(
        mine.exists(), registry().by_plane[mine].ids.del_item(reaction, missing_ok=True)
    )
    return atomic(checked >> ops.cell.remove(reaction)) >> atomic(dropped)


def clear(plane: nu.StrArg) -> nu.Nu:
    """Remove every reaction that runs ``plane``. None is fine. Cost: O(its reactions).

    One read of ``by_plane[plane]``, then each listed reaction removed
    (:func:`remove`), or only dropped from the list when it is no live
    reaction (a crash between an add's or a remove's commits left it).

    Never raises for a plane with no reactions.
    """
    ids = registry().by_plane[plane].ids
    listed = keys_of(ids)

    def one(at_: nu.Attr) -> nu.Nu:
        reaction = nu.Str(at_)
        dropped = atomic(ids.del_item(reaction, missing_ok=True))
        return nu.IfDo(atomic(_known(reaction)), remove(reaction), dropped)

    return nu.ForEachDo(atomic(listed), one)
