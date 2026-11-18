"""What local does on disk around an entry point: the space marked, flagged, checked; the uploads dir wiped.

``init`` marks the space (:func:`marked`), and flags it once its inits are
done (:func:`flagged`). Every other entry point checks that flag first
(:func:`checked`) and refuses a space without it. ``open`` looks for a
space at all before that (:func:`found`).

Each check is a query saying why not, ``""`` when fine (:data:`InitRefusal`,
:data:`MarkRefusal`, :data:`FoundRefusal`), raised by
:func:`~..blocks.guarded.refused`. Each write is a Command through
``meta.json``'s Ref or the disk's. All are steps: put them before a body
(``Guarded(body, checked(root))``) or in a flow.

A space made before ``meta.json`` (its Space store, no meta) is local's:
``init`` gives it its ``meta.json``. This is the one bridge from before. A space of the older store format
(``kernel.sqlite``) is refused: there is no converter. A ``host.lock``
left by a single-process open of before is ignored.

The uploads dir holds files tabs posted, read by workers by path: no tab
outlives the web that served it, so local wipes the dir before web starts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.errors import Missing

from ..blocks.disk import DISK, RemoveTree
from ..blocks.guarded import refused
from ..blocks.meta import MetaRef, SetInit, Stamp, is_space, read_meta
from .layout import ASSEMBLY, is_older, made_before


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "FoundRefusal",
    "InitRefusal",
    "MarkRefusal",
    "checked",
    "flagged",
    "found",
    "marked",
    "wiped",
]


def older_refusal(root: str) -> str:
    """Why ``root`` is refused for holding a space of an older store format, or ``""``."""
    if is_older(root):
        return (
            f"{root} holds a space of an older nuspace store format."
            " There is no converter: open a fresh directory."
        )
    return ""


def other_refusal(root: str) -> str:
    """Why ``root`` is refused for being another assembly's space, or ``""``.

    Raises:
        Refused: Its ``meta.json`` does not read.
    """
    meta = read_meta(root)
    if meta is not None and meta.assembly != ASSEMBLY:
        return (
            f"{root} is a space of the {meta.assembly!r} assembly, not {ASSEMBLY!r}."
            f" Open it with {meta.assembly!r}"
        )
    return ""


def mark_refusal(root: str) -> str:
    """Why ``root`` cannot be marked local's: an older space, or another assembly's. ``""`` when it can."""
    return older_refusal(root) or other_refusal(root)


def init_refusal(root: str) -> str:
    """Why ``root`` is no local space initialized: older, another assembly's, or not init. ``""`` when it is."""
    why = mark_refusal(root)
    if why:
        return why
    meta = read_meta(root)
    if meta is None or not meta.init:
        return f"the space at {root} is not initialized: run nuspace init, or local.init"
    return ""


def found_refusal(root: str) -> str:
    """Why there is no space at ``root`` at all, or ``""``. A space of any kind counts."""
    if is_space(root) or made_before(root) or is_older(root):
        return ""
    return f"no space at {root}: make one with local.init"


#: ``MarkRefusal(root)``: :func:`mark_refusal` as a query.
MarkRefusal = nu.host(mark_refusal)

#: ``InitRefusal(root)``: :func:`init_refusal` as a query.
InitRefusal = nu.host(init_refusal)

#: ``FoundRefusal(root)``: :func:`found_refusal` as a query.
FoundRefusal = nu.host(found_refusal)


def marked(root: str) -> nu.Nu:
    """The space at ``root`` checked and marked as local's: ``meta.json`` written where missing.

    Raises:
        Refused: (at run) ``root`` holds a space of an older store format,
            or one another assembly made.
    """
    return refused(MarkRefusal(root)) >> Stamp(MetaRef(root), ASSEMBLY)


def checked(root: str) -> nu.Nu:
    """The space at ``root`` checked: local's, and its init done. Writes nothing.

    Every entry point but ``init`` takes it first, so a space is refused
    before anything is made or locked.

    Raises:
        Refused: (at run) ``root`` holds a space of an older store format,
            or one another assembly made, or its ``meta.json`` is missing or
            lacks ``"init": true`` (a space made before this flag too).
    """
    return refused(InitRefusal(root))


def found(root: str) -> nu.Nu:
    """The space at ``root`` checked: there is one, of any kind. :func:`checked` comes after.

    Raises:
        Missing: (at run) No space there at all.
    """
    return refused(FoundRefusal(root), Missing)


def flagged(root: str) -> nu.Nu:
    """``"init": true`` in the ``meta.json`` of the space at ``root``: the last step of ``init``."""
    return SetInit(MetaRef(root))


def wiped(dirs: Sequence[str]) -> nu.Nu:
    """Each of ``dirs``, absolute, removed with all it holds. A missing one is fine."""
    return RemoveTree(DISK, *dirs)
