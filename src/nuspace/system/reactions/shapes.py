"""The reactions plane's own state: its reactions by the plane they run, and each reaction's plane."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Reaction", "ReactionIds", "Registry"]


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
