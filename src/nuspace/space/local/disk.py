"""What local does on disk around an entry point: its mount, the space checked, marked, flagged, its locks told.

Every entry point runs with local's mount of the data dir bound
(:func:`mounted`, ``nustd.fs`` under :data:`~.layout.DATA`), and every
file local touches there goes through it: ``meta.json``, the locks, the
session address, the uploads dir.

``init`` marks the space (:func:`marked`), the one mount that makes the
data dir, and flags it once its inits are
done (:func:`flagged`). Every other entry point is :func:`entered`: the
space checked before the mount opens (no older format, a data dir there),
then inside it (local's, its init done). ``open`` looks for a space at all
before that (:func:`found`). The mount of a driver never makes the data
dir, so a refused space is left as it was.

Each check is a query saying why not, ``""`` when fine, raised by
:func:`~..blocks.required.refused`. Each write is a write on the mount.
All are steps: put them before a body (``step >> body``) or in a flow.

A driver's lock is ``nustd.fs.Lock``, refused with ``FsLocked``;
:func:`told` turns that into local's own refusal, naming what runs where.

A space made before ``meta.json`` (its Space store, no meta) is local's:
``init`` gives it its ``meta.json``. This is the one bridge from before. A space of the older store format
(``kernel.sqlite``) is refused: there is no converter. A ``host.lock``
left by a single-process open of before is ignored.
"""

from __future__ import annotations

import os
import socket
from typing import TYPE_CHECKING

import nu
import nustd.fs
from nuspace.errors import Missing, Refused

from ..blocks.meta import data_dir, is_space, meta_in, other_refusal, set_init, stamp
from ..blocks.required import refused
from .layout import ASSEMBLY, DATA, META, is_older, made_before


if TYPE_CHECKING:
    from nustd.fs import FileRef

    from ..blocks.meta import Meta


__all__ = [
    "BareRefusal",
    "FoundRefusal",
    "InitRefusal",
    "LockRefusal",
    "OlderRefusal",
    "checked",
    "entered",
    "flagged",
    "found",
    "held",
    "marked",
    "mounted",
    "told",
]


def mounted(root: str, body: nu.Nu, *, create: bool = False) -> nu.Nu:
    """``body`` with local's mount of the data dir of ``root`` bound. Yields nothing.

    Args:
        root: The space's root, absolute.
        body: What runs with the mount bound.
        create: Make the data dir when missing: ``init`` only, every other
            entry point refuses a space without one first.
    """
    return nustd.fs.mount(str(data_dir(root)), tag=DATA, create=create, body=body)


def older_refusal(root: str) -> str:
    """Why ``root`` is refused for holding a space of an older store format, or ``""``."""
    if is_older(root):
        return (
            f"{root} holds a space of an older nuspace store format."
            " There is no converter: open a fresh directory."
        )
    return ""


def uninitialized(root: str) -> str:
    """What a refusal says of a space whose init has not run."""
    return f"the space at {root} is not initialized: run nuspace init, or local.init"


def bare_refusal(root: str) -> str:
    """Why ``root`` is refused for having no data dir at all, or ``""``: no init ever ran there."""
    return "" if data_dir(root).is_dir() else uninitialized(root)


def init_refusal(meta: Meta | None, root: str) -> str:
    """Why the space of ``meta`` at ``root`` is no local space initialized: another assembly's, or not init. ``""`` when it is."""
    why = other_refusal(meta, root, ASSEMBLY)
    if why:
        return why
    if meta is None or not meta.init:
        return uninitialized(root)
    return ""


def found_refusal(root: str) -> str:
    """Why there is no space at ``root`` at all, or ``""``. A space of any kind counts."""
    if is_space(root) or made_before(root) or is_older(root):
        return ""
    return f"no space at {root}: make one with local.init"


def lock_refusal(caught: object) -> str:
    """The refusal of a lock another holder has, from the ``FsLocked`` caught: what runs, and where."""
    exc = getattr(caught, "exception", None)
    holder = exc.holder if isinstance(exc, nustd.fs.FsLocked) else {}
    what = holder.get("what") or "component"
    host, pid = holder.get("host"), holder.get("pid")
    if pid == os.getpid() and host == socket.gethostname():
        return f"the {what} of this space runs in this process already, pid {pid}"
    where = "in a process that left no record" if pid is None else f"on {host}, pid {pid}"
    return f"the {what} of this space runs {where}. Stop it there first"


#: ``OlderRefusal(root)``: :func:`older_refusal` as a query.
OlderRefusal = nu.host(older_refusal)

#: ``BareRefusal(root)``: :func:`bare_refusal` as a query.
BareRefusal = nu.host(bare_refusal)

#: ``InitRefusal(meta, root)``: :func:`init_refusal` as a query.
InitRefusal = nu.host(init_refusal)

#: ``FoundRefusal(root)``: :func:`found_refusal` as a query.
FoundRefusal = nu.host(found_refusal)

#: ``LockRefusal(caught)``: :func:`lock_refusal` as a query.
LockRefusal = nu.host(lock_refusal)


def marked(root: str, body: nu.Nu) -> nu.Nu:
    """``body`` on the space at ``root`` marked as local's: ``meta.json`` written where missing, the mount made.

    ``init``'s way in, where :func:`entered` is every other entry point's:
    an older store format refused before the mount opens, which makes the
    data dir when missing, then the meta stamped inside it, then ``body``.
    Yields nothing.

    Raises:
        Refused: (at run) ``root`` holds a space of an older store format,
            or one another assembly made.
    """
    inside = mounted(root, stamp(META, root, ASSEMBLY) >> body, create=True)
    return refused(OlderRefusal(root)) >> inside


def checked(root: str) -> nu.Nu:
    """The space at ``root`` checked through the mount: local's, and its init done. Writes nothing.

    Raises:
        Refused: (at run) ``root`` is a space another assembly made, or its
            ``meta.json`` is missing or lacks ``"init": true`` (a space
            made before this flag too).
    """
    return refused(InitRefusal(meta_in(META, root), root))


def entered(root: str, body: nu.Nu) -> nu.Nu:
    """``body`` on the space at ``root``, initialized: checked, then run with local's mount bound.

    Before the mount opens: no older store format, a data dir there. Inside
    it, before ``body``: :func:`checked`. The mount never makes the data
    dir, so a space refused is left as it was. Every entry point but
    ``init`` runs its body through this. Yields nothing.

    Raises:
        Refused: (at run) An older store format, another assembly's space,
            or one whose init has not run.
    """
    inside = mounted(root, checked(root) >> body)
    return refused(OlderRefusal(root)) >> refused(BareRefusal(root)) >> inside


def found(root: str) -> nu.Nu:
    """The space at ``root`` checked: there is one, of any kind. Before the mount, :func:`entered` after.

    Raises:
        Missing: (at run) No space there at all.
    """
    return refused(FoundRefusal(root), Missing)


def flagged(root: str) -> nu.Nu:
    """``"init": true`` in the ``meta.json`` of the space at ``root``: the last step of ``init``."""
    return set_init(META, root)


def held(lock: FileRef) -> nu.Nu:
    """Whether some process holds ``lock``, a lock file on local's mount, now. A look, nothing taken. A query."""
    return nu.Not(nu.Is(lock.held(), None))


def told(term: nu.Nu) -> nu.Nu:
    """``term``, a lock it takes held elsewhere told as local's refusal. Yields nothing.

    ``nustd.fs.Lock`` refuses with ``FsLocked``, naming the holder's record;
    this raises ``Refused`` with what runs and where: ``the kernel of this
    space runs on red, pid 1234``. Nothing a driver runs takes an fs lock of
    its own, so every ``FsLocked`` out of ``term`` is one of its locks.
    """
    return nu.TryCatch(
        term,
        errors=nustd.fs.FsLocked,
        catch=lambda err: nu.Raise(LockRefusal(err), exc_cls=Refused),
    )
