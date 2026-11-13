"""What the ops share: the checks they make before they write, and two guarded writes.

An op reads what decides it inside its term, so under ``nuspace.atomic`` a
check and the write it guards land in one commit. Each check is one or two
point reads and raises, never writes. The error says why
(:mod:`nuspace.errors`) and names the id or key, so a caller, a person or
an agent, sees what was refused.

Literal arguments are checked at build: a key spelled wrong raises before
anything runs.

Two writes ops share: :func:`when` (a write only for a value that is not
``""``) and :func:`unkey` (a key's index entry dropped, if it is still the
row's).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.errors import Ended, Exists, Missing, Refused, Removed
from nuspace.shapes.exec import EXITS

from .interactions import InKeyChars, in_key_chars


if TYPE_CHECKING:
    import nustd.kv


__all__ = [
    "anchored",
    "exit_known",
    "id_spelled",
    "key_free",
    "key_spelled",
    "live",
    "not_ended",
    "refuse",
    "row_known",
    "text",
    "unkey",
    "when",
]


def text(*parts: object) -> object:
    """A message from parts, any of them a term: a plain str when every part is one."""
    if all(isinstance(p, str) for p in parts):
        return "".join(parts)  # type: ignore[arg-type]
    out = nu.Str(parts[0])
    for part in parts[1:]:
        out = out + nu.Str(part)
    return out


def refuse(cond: object, exc: type[BaseException], *msg: object) -> nu.Nu:
    """Raise ``exc`` with ``msg`` when ``cond`` reads true. NULL reads false."""
    return nu.IfDo(cond, nu.Raise(text(*msg), exc_cls=exc))


def row_known(rows: nustd.kv.DictRef, id: nu.StrArg, what: str) -> nu.Nu:
    """``id`` has a row in ``rows``.

    Raises:
        Missing: No row with that id.
    """
    return refuse(rows.contains(id).not_(), Missing, "no ", what, " ", id)


def live(rows: nustd.kv.DictRef, id: nu.StrArg, what: str) -> nu.Nu:
    """``id`` has a row in ``rows`` and it is not removed. Two point reads.

    Raises:
        Missing: No row with that id.
        Removed: The row is removed.
    """
    return row_known(rows, id, what) >> refuse(
        rows[id].removed_at.exists(), Removed, what, " ", id, " is removed"
    )


def anchored(
    listed: nustd.kv.OrderedDictRef,
    rows: nustd.kv.DictRef,
    anchor: nu.StrArg | None,
    id: nu.StrArg,
    what: str,
    where: str,
) -> nu.Nu:
    """``anchor``, when one is given, is a live row listed in ``listed``, and not ``id`` itself.

    Args:
        listed: The list the id goes into: a plane's ``children`` or ``cells``.
        rows: Where the anchor's row is: ``Space.planes`` or ``Space.cells``.
        anchor: The ``before`` or ``after`` id, None for the end.
        id: The id being placed.
        what: The anchor's kind, for the message.
        where: Where it must be listed, for the message.

    Raises:
        Missing: No row with the anchor's id.
        Removed: The anchor is removed.
        Refused: The anchor is the id itself, or is not listed there.
    """
    if anchor is None:
        return nu.Noop()
    if isinstance(anchor, str) and isinstance(id, str) and anchor == id:
        msg = f"{what} {id} cannot be placed next to itself"
        raise Refused(msg)
    return (
        live(rows, anchor, what)
        >> refuse(nu.Str(anchor) == id, Refused, what, " ", id, " cannot be placed next to itself")
        >> refuse(listed.contains(anchor).not_(), Refused, what, " ", anchor, " is not on ", where)
    )


def key_spelled(key: nu.StrArg, what: str, *, empty_ok: bool) -> nu.Nu:
    """``key`` is key chars, or ``""`` (no key) when ``empty_ok``.

    Key chars are letters of either case, digits, ``_`` and ``-``; case is
    kept and compared. A literal key is checked at build, a term when it
    evaluates.

    Raises:
        Refused: The key is empty (unless ``empty_ok``) or not key chars.
    """
    spelled = f"{what} keys are key chars: letters, digits, _ and -"
    if isinstance(key, str):
        if key == "" and empty_ok:
            return nu.Noop()
        if key == "":
            raise Refused(f"empty {what} key")
        if not in_key_chars(key):
            raise Refused(f"{what} key {key!r}: {spelled}")
        return nu.Noop()
    bad = nu.Bool(InKeyChars(key)).not_()
    if empty_ok:
        bad = (nu.Str(key) != "").and_(bad)
    else:
        bad = (nu.Str(key) == "").or_(bad)
    return refuse(bad, Refused, what, " key ", key, ": ", spelled)


def id_spelled(id: nu.StrArg, what: str) -> nu.Nu:
    """A caller given ``id`` is key chars, as keys are: ids are slugs.

    An id lands in urls (``/p/<plane>``) and paths, so it holds only what
    reads the same everywhere. Minted ids (``p_<hex>_<hex>_<hex>``) and the
    system and reserved ones pass. A literal id is checked at build, a term
    when it evaluates.

    Raises:
        Refused: The id is empty or not key chars.
    """
    spelled = f"{what} ids are key chars: letters, digits, _ and -"
    if isinstance(id, str):
        if not in_key_chars(id):
            raise Refused(f"{what} id {id!r}: {spelled}")
        return nu.Noop()
    return refuse(nu.Bool(InKeyChars(id)).not_(), Refused, what, " id ", id, ": ", spelled)


def key_free(index: nustd.kv.DictRef, key: nu.StrArg, owner: nu.StrArg | None, what: str) -> nu.Nu:
    """No other live row holds ``key`` in ``index``. One point read.

    Args:
        index: ``Space.indexes.plane_keys`` or ``cell_keys``.
        key: The key, ``""`` for none (nothing to check).
        owner: The row that may hold it already, None for a new row.
        what: The kind, for the message.

    Raises:
        Exists: Another row holds the key.
    """
    held = index.get_item(key, "")
    taken = held != "" if owner is None else (held != "").and_(held != owner)
    if not isinstance(key, str):
        taken = (nu.Str(key) != "").and_(taken)
    elif key == "":
        return nu.Noop()
    return refuse(taken, Exists, what, " key ", key, " is taken")


def not_ended(rows: nustd.kv.DictRef, id: nu.StrArg, what: str) -> nu.Nu:
    """``id`` has a row in ``rows`` and it has not ended.

    Raises:
        Missing: No row with that id.
        Ended: It already ended.
    """
    return row_known(rows, id, what) >> refuse(
        rows[id].ended_at.exists(), Ended, what, " ", id, " already ended"
    )


def exit_known(exit: nu.StrArg) -> nu.Nu:
    """``exit`` is one of :data:`~nuspace.shapes.exec.EXITS`. A literal is checked at build.

    Raises:
        Refused: Any other exit.
    """
    if isinstance(exit, str):
        if exit not in EXITS:
            raise Refused(f"exit {exit!r} is none of {EXITS}")
        return nu.Noop()
    return refuse(nu.List.of(*EXITS).contains(exit).not_(), Refused, "exit ", exit, " is unknown")


def when(value: nu.StrArg, write: nu.Nu) -> nu.Nu:
    """``write`` when ``value`` is not ``""``. A literal decides at build."""
    if isinstance(value, str):
        return write if value else nu.Noop()
    return nu.IfDo(nu.Str(value) != "", write)


def unkey(index: nustd.kv.DictRef, key: nu.Nu, owner: nu.StrArg) -> nu.Nu:
    """Drop ``key`` from ``index`` when ``owner`` still holds it there. One point read.

    For a row being removed: its ``.key`` stays on the row, its index entry
    goes, unless another row took the key since. A NULL or ``""`` key drops
    nothing.

    Args:
        index: ``Space.indexes.plane_keys`` or ``cell_keys``.
        key: The row's ``.key`` ref.
        owner: The row's id.
    """
    held = key.fallback("")
    return nu.IfDo((held != "").and_(index.get_item(held, "") == owner), index.del_item(held))
