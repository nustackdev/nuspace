"""The reactions plane's own state: the plane's id, its reactions by the plane they run, and each reaction's plane."""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.places import at


__all__ = ["PLANE", "Reaction", "ReactionIds", "Registry", "registry"]


#: The plane's id, fixed.
PLANE = "reactions"


class Reaction(nu.Shape):
    """One reaction's own cell state, at ``State.cells[reaction]``.

    ``plane`` is the plane it runs, written at add, so remove finds the
    reaction's entry in :attr:`Registry.by_plane` with one read, no scan.
    ``run`` is the plane run it last asked for, absent before the first:
    the only run it ever checks, so runs others start are theirs.
    """

    plane = nustd.kv.StrRef.slot()
    run = nustd.kv.StrRef.slot()


class ReactionIds(nu.Shape):
    """The reactions that run one plane: ``Registry.by_plane[plane].ids``, a set."""

    ids = nustd.kv.DictRef.slot(bool)


class Registry(nu.Shape):
    """The reactions plane's state, at ``State.planes["reactions"]``.

    ``by_plane[plane].ids`` lists the reactions that run ``plane``, what
    ``reactions.clear(plane)`` reads.
    """

    by_plane = nustd.kv.DictRef.slot(ReactionIds)


def registry() -> Registry:
    """The plane's state: ``State.planes["reactions"]`` read through :class:`Registry`."""
    return at.plane(id=PLANE).state(Registry)
