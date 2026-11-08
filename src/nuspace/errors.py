"""What an op raises when it cannot do what it says.

Ops raise, never fail silently: the commit aborts and the caller sees why.
Five errors, one per reason, all under :class:`NuspaceError`, a
``LookupError``, so one ``except`` catches every refusal an op makes:

- :class:`Missing`: no row, entry or list member with that id or key.
- :class:`Removed`: the row is there, but removed.
- :class:`Exists`: an id or key is taken, or a member is already listed.
- :class:`Refused`: the request is not allowed: a system plane, root, a
  cycle, an anchor that is not a sibling, a key that is not key chars, a
  store of another format.
- :class:`Ended`: the run or worker already ended.

Strict by default. An op may take a ``<state>_ok=True`` opt-out
(``exists_ok``, ``missing_ok``, ...) where a real caller means "make sure";
its doc lists the ones it takes. Reads that may find nothing give NULL and
raise nothing.

An op raises at run time with ``nu.Raise``::

    nu.IfDo(Space.planes[plane].exists().not_(), nu.Raise("no such plane", exc_cls=Missing))
"""

from __future__ import annotations


__all__ = [
    "Ended",
    "Exists",
    "Missing",
    "NuspaceError",
    "Refused",
    "Removed",
]


class NuspaceError(LookupError):
    """Base of every error a nuspace op raises. Catch it to handle them all alike."""


class Missing(NuspaceError):  # noqa: N818 -- the design's names: the reason, not the type
    """No row, index entry or list member with that id or key."""


class Removed(NuspaceError):  # noqa: N818 -- the design's names: the reason, not the type
    """The row exists but is removed: it is kept and readable, and no op acts on it."""


class Exists(NuspaceError):  # noqa: N818 -- the design's names: the reason, not the type
    """An id or key is taken by a live row, or a member is already listed."""


class Refused(NuspaceError):  # noqa: N818 -- the design's names: the reason, not the type
    """Not allowed: a system plane, root, a cycle, a bad anchor or key, a store of another format."""


class Ended(NuspaceError):  # noqa: N818 -- the design's names: the reason, not the type
    """The run or worker already ended, so it cannot start or end again."""
