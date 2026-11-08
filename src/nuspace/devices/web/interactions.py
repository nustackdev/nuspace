"""The web device's own nu interactions: small reads over plain values, kept out of the op and feed files.

- :data:`ErrorType`, :data:`ErrorMessage`: a caught error's type name and
  its message, what a toast says.
- :data:`Session`: the tab a plane run draws on, read off its env specs.
- :data:`Href`: a pane's URL, encoded the way the browser does.
- :data:`IconName`: a stored icon as a page link takes it.
- :class:`EventField`: one field off a browser event, strict.

Safe for a worker to import: nothing here pulls in a server.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING
from urllib.parse import quote

import nu
import nustd.ui
from nu.lang import ScalarQuery


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = [
    "SESSION_ENV",
    "ErrorMessage",
    "ErrorType",
    "EventField",
    "Href",
    "IconName",
    "Session",
]


#: The name the session env factory is registered under, and the first item
#: of a run's env spec for a tab: ``["session", sid]``.
SESSION_ENV = "session"


def _exception(error: object) -> BaseException | None:
    """The live exception a ``TryCatch`` bound, when it bound one."""
    held = getattr(error, "exception", None)
    return held if isinstance(held, BaseException) else None


def _error_type(error: object) -> str:
    held = _exception(error)
    return type(held).__name__ if held is not None else "Error"


def _error_message(error: object) -> str:
    held = _exception(error)
    return str(held) if held is not None else str(error)


#: ``ErrorType(err)``: the class name of a caught error, ``Missing``, ``Refused``, ``KeyError``.
ErrorType = nu.host(_error_type, name="ErrorType")

#: ``ErrorMessage(err)``: a caught error's message, as ``str(exc)`` says it.
ErrorMessage = nu.host(_error_message, name="ErrorMessage")


def _session(envs: object) -> str:
    # A run's envs are the specs it was asked with, ``[["session", sid]]``
    # for a pane nav runs. "" for a run with no tab.
    for spec in envs if isinstance(envs, Sequence) else ():
        if isinstance(spec, Sequence) and len(spec) > 1 and spec[0] == SESSION_ENV:
            return str(spec[1])
    return ""


#: ``Session(envs)``: the tab id a plane run's env specs name, ``""`` for a run on no tab.
Session = nu.host(_session, name="Session")


def _href(plane: object, given: object) -> str:
    pairs = given if isinstance(given, Mapping) else {}
    search = nustd.ui.encode_query(dict(pairs))
    # encodeURIComponent's set, so a plane id reads the same on both sides.
    path = "/" + quote(str(plane), safe="!*'()")
    return f"{path}?{search}" if search else path


#: ``Href(plane, params)``: ``/<plane>``, or ``/<plane>?<params>``; a None param drops its key.
Href = nu.host(_href, name="Href")


def _icon_name(icon: object) -> str:
    # A stored icon is ``lucide:<name>`` or ``emoji:<char>``; a page link
    # takes the bare name or the character.
    text = "" if icon is None else str(icon)
    return text.partition(":")[2] if ":" in text else text


#: ``IconName(icon)``: a stored icon as a page link takes it, its prefix dropped.
IconName = nu.host(_icon_name, name="IconName")


def _ids(held: object) -> bool:
    return isinstance(held, list) and all(isinstance(i, str) for i in held)


#: What :class:`EventField` checks a field against: a test and what it says.
_KINDS: dict[str, tuple[Callable[[object], bool], str]] = {
    "str": (lambda v: isinstance(v, str), "a string"),
    "bool": (lambda v: isinstance(v, bool), "a bool"),
    "dict": (lambda v: isinstance(v, dict), "a dict"),
    "ids": (_ids, "a list of ids"),
    # An anchor may be left out: it reads "", the end.
    "anchor": (lambda v: v is None or isinstance(v, str), "an id"),
}


class EventField(ScalarQuery):
    """One field off a browser event, strict: present and of the kind asked, or a raise.

    A malformed event never runs an op on a guess: its guard toasts the
    raise like any other failure.

    Args:
        row: The event.
        field: The field's name.
        kind: ``"str"``, ``"bool"``, ``"dict"``, ``"ids"`` (a list of
            strings) or ``"anchor"`` (a string, or absent for ``""``).

    Raises:
        ValueError: The field is absent or of another kind. At build, a
            kind none of these.
    """

    def __init__(self, row: nu.Nu, field: str, kind: str) -> None:
        if kind not in _KINDS:
            msg = f"EventField kind {kind!r} is none of {sorted(_KINDS)}"
            raise ValueError(msg)
        super().__init__(row)
        self._payload["field"] = field
        self._payload["kind"] = kind

    def _read(self, row: object) -> object:
        field, kind = self._payload["field"], self._payload["kind"]
        test, what = _KINDS[kind]
        held = row.get(field) if isinstance(row, Mapping) else None
        if not test(held):
            msg = f"malformed event: {field!r} must be {what}, got {held!r}"
            raise ValueError(msg)
        if kind == "anchor":
            return held or ""
        return list(held) if isinstance(held, list) else held

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (row,) = children

        def thunk(rt: Runtime) -> object:
            return self._read(row(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (row,) = children

        async def athunk(rt: Runtime) -> object:
            return self._read(await row(rt))

        return athunk
