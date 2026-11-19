"""What local does on disk around an entry point: its mounts, the space checked, marked, flagged, its locks told.

Every entry point runs with two mounts of local's bound (``nustd.fs``): a
read only one over the space's root (:func:`rooted`, :data:`~.layout.ROOT`),
and inside it one over the data dir (:func:`mounted`, :data:`~.layout.DATA`),
opened at ``ROOT.where(".nuspace")``. Every file local touches goes through
them: the checks before the data dir opens look through the root's,
``meta.json``, the locks, the session address and the uploads dir sit on
the data dir's. The root may be a term, eg a temp dir's ``where()``: it is
read when the mounts open.

``init`` marks the space (:func:`marked`), the one entry point whose
mounts make the root and the data dir, and flags it once its inits are
done (:func:`flagged`). Every other entry point is :func:`entered`: the
root there, then the space checked through the root's mount (no older
format, a data dir there), then inside the data dir's (local's, its init
done). ``open`` looks for a space at all before that. The mounts of a
driver never make anything, so a refused space is left as it was.

Each check is a step (``step >> body``): a query on a mount, raised by
:func:`~..blocks.required.refused` with a ``Str`` formatted at run. Each
write is a write on the data dir's mount.

A driver's lock is ``nustd.fs.Lock``, refused with ``FsLocked``;
:func:`told` turns that into local's own refusal, naming what runs where
from the holder's record.

A space made before ``meta.json`` (its Space store, no meta) is local's:
``init`` gives it its ``meta.json``. This is the one bridge from before. A space of the older store format
(``kernel.sqlite``) is refused: there is no converter. A ``host.lock``
left by a single-process open of before is ignored.
"""

from __future__ import annotations

from functools import reduce
from typing import TYPE_CHECKING

import nu
import nustd.fs
from nuspace.errors import Missing, Refused

from ..blocks.meta import DATA_DIR, META_FILE, meta_in, not_other, ran, said, set_init, stamp
from ..blocks.required import refused
from .layout import ASSEMBLY, DATA, MADE_BEFORE, META, OLDER, ROOT


if TYPE_CHECKING:
    from nustd.fs import FileRef


__all__ = [
    "checked",
    "entered",
    "flagged",
    "held",
    "is_older",
    "is_space",
    "made_before",
    "marked",
    "mounted",
    "rooted",
    "told",
]


def rooted(root: str | nu.Nu, body: nu.Nu, *, create: bool = False) -> nu.Nu:
    """``body`` with local's read only mount of the space's root bound. Yields nothing.

    It follows any symlink: a data dir linked elsewhere is the space's own.

    Args:
        root: The space's root, a path or a term yielding one.
        body: What runs with the mount bound.
        create: Make the root when missing: ``init`` only.
    """
    return nustd.fs.mount(root, tag=ROOT, readonly=True, create=create, follow="any", body=body)


def mounted(body: nu.Nu, *, create: bool = False) -> nu.Nu:
    """``body`` with local's mount of the data dir bound, inside :func:`rooted`. Yields nothing.

    Args:
        body: What runs with the mount bound.
        create: Make the data dir when missing: ``init`` only, every other
            entry point refuses a space without one first.
    """
    return nustd.fs.mount(ROOT.where(DATA_DIR), tag=DATA, create=create, body=body)


def _file(name: str) -> nu.Nu:
    """Whether the file ``name``, relative to the root, is there. On the root's mount."""
    return ROOT.has(name, kind="file")


def is_space() -> nu.Nu:
    """Whether the root is a space: its data dir holds ``meta.json``. On the root's mount."""
    return _file(f"{DATA_DIR}/{META_FILE}")


def made_before() -> nu.Nu:
    """Whether the root holds a local space made before ``meta.json``: its Space store and no meta."""
    return nu.And(nu.Not(is_space()), _file(f"{DATA_DIR}/{MADE_BEFORE}"))


def _any_older() -> nu.Nu:
    return nu.Or(*(_file(f"{DATA_DIR}/{f}") for f in OLDER), *(_file(f) for f in OLDER))


def is_older() -> nu.Nu:
    """Whether the root holds a space of an older store format, and none of this one."""
    return nu.And(nu.Not(is_space()), nu.Not(made_before()), _any_older())


def uninitialized(root: nu.StrArg) -> nu.Str:
    """What a refusal says of a space whose init has not run."""
    return said(
        "the space at {root} is not initialized: run nuspace init, or local.init", root=root
    )


def older() -> nu.Nu:
    """The root refused for holding a space of an older store format. A step on the root's mount."""
    why = said(
        "{root} holds a space of an older nuspace store format."
        " There is no converter: open a fresh directory.",
        root=ROOT.where(),
    )
    return refused(is_older(), why)


def bare() -> nu.Nu:
    """The root refused for having no data dir at all: no init ever ran there. A step on the root's mount."""
    return refused(nu.Not(ROOT.has(DATA_DIR, kind="dir")), uninitialized(ROOT.where()))


def found() -> nu.Nu:
    """The root refused as ``Missing`` for holding no space of any kind. A step on the root's mount."""
    why = said("no space at {root}: make one with local.init", root=ROOT.where())
    return refused(nu.Not(nu.Or(is_space(), made_before(), _any_older())), why, Missing)


def there(root: str | nu.Nu, why: nu.Str, exc_cls: type[Exception]) -> nu.Nu:
    """The root there as a directory, or ``exc_cls(why)``: a mount over it opened and closed. A step.

    A mount that does not make its dir refuses a missing one with
    ``FileNotFoundError``; this tells it as local's refusal before anything
    else looks.
    """
    return nu.TryCatch(
        rooted(root, nu.Noop()),
        errors=(FileNotFoundError, NotADirectoryError),
        catch=nu.Raise(why, exc_cls=exc_cls),
    )


def marked(root: str | nu.Nu, body: nu.Nu) -> nu.Nu:
    """``body`` on the space at ``root`` marked as local's: the root and data dir made, ``meta.json`` written where missing.

    ``init``'s way in, where :func:`entered` is every other entry point's:
    the root's mount made, an older store format refused through it, the
    data dir's mount made, then the meta stamped inside it, then ``body``.
    Yields nothing.

    Raises:
        Refused: (at run) ``root`` holds a space of an older store format,
            or one another assembly made.
    """
    inside = mounted(stamp(META, ROOT.where(), ASSEMBLY) >> body, create=True)
    return rooted(root, older() >> inside, create=True)


def checked() -> nu.Nu:
    """The space checked through the data dir's mount: local's, and its init done. Writes nothing.

    Raises:
        Refused: (at run) The space is another assembly's, or its
            ``meta.json`` is missing or lacks ``"init": true`` (a space
            made before this flag too).
    """
    where = ROOT.where()
    return nu.let(
        meta_in(META),
        lambda meta: (
            not_other(meta, where, ASSEMBLY) >> refused(nu.Not(ran(meta)), uninitialized(where))
        ),
    )


def entered(root: str | nu.Nu, body: nu.Nu, *, any_space: bool = False) -> nu.Nu:
    """``body`` on the space at ``root``, initialized: checked, then run with local's mounts bound.

    The root there, then through its mount: no older store format, a data
    dir there. Inside the data dir's mount, before ``body``: :func:`checked`.
    Neither mount makes anything, so a space refused is left as it was.
    Every entry point but ``init`` runs its body through this. Yields nothing.

    Args:
        root: The space's root, a path or a term yielding one.
        body: What runs inside.
        any_space: Refuse a root holding no space of any kind as
            ``Missing`` first, as ``open`` does.

    Raises:
        Missing: (at run) With ``any_space``, no space there at all.
        Refused: (at run) An older store format, another assembly's space,
            or one whose init has not run.
    """
    if any_space:
        gone = there(root, said("no space at {root}: make one with local.init", root=root), Missing)
        steps = [found(), older(), bare()]
    else:
        gone = there(root, uninitialized(root), Refused)
        steps = [older(), bare()]
    inside = reduce(lambda a, b: a >> b, [*steps, mounted(checked() >> body)])
    return gone >> rooted(root, inside)


def flagged() -> nu.Nu:
    """``"init": true`` in the space's ``meta.json``: the last step of ``init``, inside its mounts."""
    return set_init(META, ROOT.where())


def held(lock: FileRef) -> nu.Nu:
    """Whether some process holds ``lock``, a lock file on local's mount, now. A look, nothing taken. A query."""
    return nu.Not(nu.Is(lock.held(), None))


def lock_refusal(err: nu.Nu) -> nu.Str:
    """The refusal of a lock another holder has, from the ``FsLocked`` caught: what runs, and where."""
    holder = nu.Dict(nu.GetAttr(nu.GetAttr(err, "exception"), "holder"))
    what, host, pid = (holder.get_item(k, None) for k in ("what", "host", "pid"))
    where = nu.If(
        nu.Is(pid, None),
        "in a process that left no record",
        said("on {host}, pid {pid}", host=host, pid=pid),
    )
    return said(
        "the {what} of this space runs {where}. Stop it there first",
        what=nu.If(what, what, "component"),
        where=where,
    )


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
        catch=lambda err: nu.Raise(lock_refusal(err), exc_cls=Refused),
    )
