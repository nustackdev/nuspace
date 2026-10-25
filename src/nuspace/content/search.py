"""Finding items: the scopes holding a kind, the items ``match`` holds for, and the walk over both.

Search is by kind: per kind it walks the store's ``cells``, then ``planes``,
then ``space`` (:mod:`nuspace.shapes.contents`), and checks each item with
the kind's ``match``. What a search does with the ids it finds, eg the
Search plane appending hits (:mod:`nuspace.system.ui.search`), is the
caller's: :func:`walk` hands them over, a scope at a time.

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

import nu
import nustd.kv
from nuspace.ext.registry import kind_name
from nuspace.shapes import States

from .kind import CELL, PLANE, SLOTS, SPACE


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .kind import Content


__all__ = ["asked", "matched", "scopes", "walk"]


def scopes(kind: type[Content[Any]], level: str) -> nu.List:
    """The ids of the scopes at ``level`` holding items of ``kind``: cells or planes. A bare read.

    Raises:
        ValueError: ``level`` is :data:`~nuspace.content.SPACE`, one scope only, or none of
            :data:`~nuspace.content.LEVELS`.
    """
    if level not in SLOTS:
        msg = f"scope level {level!r} is none of {tuple(SLOTS)}"
        raise ValueError(msg)
    return nu.list(getattr(States.contents[kind_name(kind)], SLOTS[level]).keys())


def matched(
    kind: type[Content[Any]], scope: tuple[str, nu.StrArg], question: Mapping[str, Any]
) -> nu.Iterator:
    """The ids of the items in ``scope`` that ``kind``'s :meth:`~nuspace.content.Content.match` holds for.

    A bare read. The one check a search and :meth:`~nuspace.content.Content.find`
    both make, per scope.

    Args:
        kind: The kind.
        scope: ``(level, id)``, as :meth:`~nuspace.content.Content.at` takes it.
        question: ``match``'s keywords.
    """
    held = kind.items(scope)
    return (
        nu.list(held.keys())
        .iter()
        .filter(lambda found: kind.match(kind.at(scope, nu.Str(found)), **question))
    )


def asked(kind: type[Content[Any]], keywords: Mapping[str, Any]) -> dict[str, Any]:
    """The keywords ``kind``'s ``match`` takes, the rest dropped: a form older than the kind asks no more."""
    params = inspect.signature(kind.match).parameters
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(keywords)
    return {k: v for k, v in keywords.items() if k in params}


def walk(
    kind: type[Content[Any]],
    keywords: Mapping[str, Any],
    found: Callable[[tuple[str, nu.StrArg], nu.ObjectRef], nu.Nu],
) -> nu.Nu:
    """Every item of one kind searched: its cells, then its planes, then the space's.

    Per scope its matches are read in a snapshot of their own, then handed to
    ``found`` with the scope, so nothing is held open across the walk. The
    keywords are filtered to what ``match`` takes (:func:`asked`).

    Args:
        kind: The kind.
        keywords: ``match``'s keywords; one left out stays ``UNSET``.
        found: ``(scope, ids)`` to what is done with one scope's hits, its
            ids a list, possibly empty. Its writes are its own to bracket.
    """
    question = asked(kind, keywords)

    def snap(term: nu.Nu) -> nu.Nu:
        return nustd.kv.Snapshot(term, scope=States)

    def one(level: str, scope_id: nu.StrArg) -> nu.Nu:
        scope = (level, scope_id)
        return nu.let(snap(matched(kind, scope, question).to_list()), lambda ids: found(scope, ids))

    def each(level: str) -> nu.Nu:
        return nu.ForEachDo(snap(scopes(kind, level)), lambda at: one(level, nu.Str(at)))

    return each(CELL) >> each(PLANE) >> one(SPACE, "")
