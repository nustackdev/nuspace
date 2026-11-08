"""Content kinds for the content and search tests. A module of its own so a worker can import it.

``NoteContent`` asks three things, one per input a form generates;
``PlainContent`` keeps every default: no question, draws nothing.
"""

from __future__ import annotations

import nu
import nustd.kv
import nustd.ui
from nuspace.shapes.content import UNSET, Content, Unset, entries


class Note(nu.Shape):
    body = nustd.kv.StrRef.slot()
    stars = nustd.kv.FloatRef.slot()
    done = nustd.kv.BoolRef.slot()


class Shown(nustd.ui.Column):
    """How a note draws as a hit."""

    body = nustd.ui.TextRef.slot()


class NoteContent(Content[Note], name="Note"):
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


class PlainContent(Content[Note], name="Plain"):
    pass


def write(kind: type[Content], scope: tuple[str, str], key: str, **fields: object) -> nu.Nu:
    """One item's fields set at ``scope``, ``(level, id)``, as a program keeping it would. One commit."""
    at = entries(kind, *scope)[key]
    writes = nu.Sequential(*[getattr(at, k).set(v) for k, v in fields.items()])
    return nustd.kv.atomic(writes)
