"""The disk as a fabric: what an assembly writes on the file system, as Commands through one Ref.

An entry point makes dirs, wipes a dir, writes a small file whole. Those
are writes, so they go through a Ref like any write (``nu.Print`` through
``STDOUT`` is the model): :data:`DISK` sits in slot 0 of each Command,
declared in ``mutates``, so the engine keeps them ordered and never folds
one away as a pure read.

- :class:`DiskBackend`: the file system the Commands act on. The real one
  unless a test binds its own on the Context.
- :class:`DiskRef`, :data:`DISK`: the Ref. Its read yields the backend.
- :data:`MakeDirs`, :data:`RemoveTree`, :data:`WriteWhole`,
  :data:`RemoveIfHolds`: the Commands, each a ``nu.host`` over the backend.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Context, Runtime


__all__ = [
    "DISK",
    "DiskBackend",
    "DiskRef",
    "MakeDirs",
    "RemoveIfHolds",
    "RemoveTree",
    "WriteWhole",
]


class DiskBackend:
    """The file system the disk Commands act on. Bind a subclass on the Context to redirect them.

    Every write is idempotent: a dir there already, a tree gone already, a
    file not holding what it should, all are fine.
    """

    def make_dirs(self, path: str) -> None:
        """``path`` made with its parents, where missing."""
        Path(path).mkdir(parents=True, exist_ok=True)

    def remove_tree(self, path: str) -> None:
        """``path`` removed with all it holds, where there."""
        shutil.rmtree(path, ignore_errors=True)

    def write_whole(self, path: str, text: str) -> None:
        """``text`` written to ``path`` through a temp file and a replace: a reader never sees half."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        Path(tmp).replace(target)

    def remove_if_holds(self, path: str, text: str) -> None:
        """``path`` removed only while it holds ``text``, stripped: a later writer keeps its own."""
        target = Path(path)
        try:
            if target.read_text(encoding="utf-8").strip() == text.strip():
                target.unlink()
        except FileNotFoundError:
            pass


#: The real file system, when the Context binds no backend.
REAL = DiskBackend()


def disk_of(ctx: Context) -> DiskBackend:
    """The backend bound on ``ctx``, else the real file system."""
    return ctx.fabrics.get(DiskBackend) if ctx.fabrics.has(DiskBackend) else REAL


class DiskRef(nu.Ref):
    """The Ref naming the disk, what the disk Commands write. One: :data:`DISK`.

    Like ``nu.StdioRef`` it has no address child: the Commands carry their
    paths. Its read yields the backend, which a ``nu.host`` Command gets
    as its first argument.

    Yields:
        The :class:`DiskBackend` in effect.
    """

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> DiskBackend:
            return disk_of(rt.ctx)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> DiskBackend:
            return disk_of(rt.ctx)

        return athunk

    def _write(self, rt: Runtime, value: tuple[str, str], nid: int) -> None:
        """``value``, a ``(path, text)`` pair, written whole: the fabric's WRITE half."""
        path, text = value
        disk_of(rt.ctx).write_whole(path, text)

    async def _awrite(self, rt: Runtime, value: tuple[str, str], nid: int) -> None:
        """Async sibling of :meth:`_write`: a small file, sync work."""
        self._write(rt, value, nid)


#: The disk.
DISK = DiskRef()


def make_dirs(disk: DiskBackend, *paths: str) -> None:
    """Each of ``paths`` made with its parents, where missing."""
    for path in paths:
        disk.make_dirs(path)


def remove_tree(disk: DiskBackend, *paths: str) -> None:
    """Each of ``paths`` removed with all it holds, where there."""
    for path in paths:
        disk.remove_tree(path)


def write_whole(disk: DiskBackend, path: str, text: str) -> None:
    """``text`` written to ``path`` whole."""
    disk.write_whole(path, text)


def remove_if_holds(disk: DiskBackend, path: str, text: str) -> None:
    """``path`` removed only while it holds ``text``."""
    disk.remove_if_holds(path, text)


WRITES = frozenset({0})

#: ``MakeDirs(DISK, *paths)``: each dir made with its parents, where missing.
MakeDirs = nu.host(make_dirs, base=nu.Command, mutates=WRITES)

#: ``RemoveTree(DISK, *paths)``: each dir removed with all it holds, where there.
RemoveTree = nu.host(remove_tree, base=nu.Command, mutates=WRITES)

#: ``WriteWhole(DISK, path, text)``: the file written through a replace, never seen half.
WriteWhole = nu.host(write_whole, base=nu.Command, mutates=WRITES)

#: ``RemoveIfHolds(DISK, path, text)``: the file removed only while it holds ``text``.
RemoveIfHolds = nu.host(remove_if_holds, base=nu.Command, mutates=WRITES)
