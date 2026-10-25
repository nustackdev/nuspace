"""Content kinds for the content and search tests. A module of its own so a worker can import it.

``NoteContent`` asks three things, one per input a form generates;
``PlainContent`` keeps every default: no question, draws nothing.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.content import UNSET, Unset


class Note(nu.Shape):
    body = nustd.kv.StrRef.slot()
    stars = nustd.kv.FloatRef.slot()
    done = nustd.kv.BoolRef.slot()


class Shown(nustd.ui.Column):
    """How a note draws as a hit."""

    body = nustd.ui.TextRef.slot()


class NoteContent(nuspace.Content[Note], name="Note"):
    @classmethod
    def match(
        cls,
        item: Note,
        *,
        text: nu.StrArg | Unset = UNSET,
        min_stars: nu.FloatArg | Unset = UNSET,
        done: nu.BoolArg | Unset = UNSET,
    ) -> nu.Bool:
        checks: list[nu.Nu] = []
        if text is not UNSET:
            body = nu.Str(item.body.fallback("")).lower()
            checks.append(body.contains(nu.Str(text).lower()))
        if min_stars is not UNSET:
            checks.append(nu.Float(item.stars.fallback(0.0)) >= min_stars)
        if done is not UNSET:
            checks.append(nu.Bool(item.done.fallback(False)) == done)
        return nu.And(*checks) if checks else nu.Bool(True)

    @classmethod
    def render_hit(cls, item: Note) -> nu.Nu:
        return Shown.body.set(item.body)


class PlainContent(nuspace.Content[Note], name="Plain"):
    pass


def write(
    kind: type[nuspace.Content], scope: tuple[str, str], item: str, **fields: object
) -> nu.Nu:
    """One item's fields set, as a program keeping it would. One commit."""
    at = kind.at(scope, item)
    writes = nu.Sequential(*[getattr(at, k).set(v) for k, v in fields.items()])
    return nuspace.ops.atomic_state(writes)
