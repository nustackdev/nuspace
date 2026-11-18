"""What every assembly shares about a space on disk: the data dir, ``meta.json``, how a space is found, its root.

A space is a directory, any one, its data kept in ``.nuspace/`` the way a
repository keeps ``.git/``. One file in it is common to every assembly::

    <space root>/
      .nuspace/
        meta.json      {"assembly": "local", "made_at": "<iso time>", "init": true}
        ...            the rest is the assembly's own layout

``meta.json`` marks the space and names the assembly that made it, so a
tool knows which assembly opens it. ``init`` says whether the assembly's
init ran to its end: a plain flag, false until then, false when missing. ``~/.nuspace`` holds the user's
config whether or not home is a space: a data dir alone is no space.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, cast

import nu
from nu.engine.structure import Declared
from nuspace.errors import Refused

from .disk import DISK, REAL, MakeDirs, disk_of


if TYPE_CHECKING:
    import os
    from collections.abc import Callable, Sequence

    from nu.lang.runtime import Runtime


__all__ = [
    "DATA_DIR",
    "META_FILE",
    "InitDone",
    "Meta",
    "MetaRef",
    "SetInit",
    "Stamp",
    "data_dir",
    "data_made",
    "find_space",
    "init_done",
    "is_space",
    "read_meta",
    "resolve_root",
    "write_meta",
]


#: The directory inside a space's root holding its data.
DATA_DIR = ".nuspace"

#: The one file every assembly keeps in :data:`DATA_DIR`.
META_FILE = "meta.json"


@dataclass(frozen=True)
class Meta:
    """What ``meta.json`` says.

    Attributes:
        assembly: The name of the assembly that made the space, eg ``"local"``.
        made_at: When ``meta.json`` was written, an ISO 8601 time in UTC.
        init: Whether the assembly's init ran to its end on the space.
    """

    assembly: str
    made_at: str
    init: bool = False


def data_dir(root: str | os.PathLike[str]) -> Path:
    """The data dir of the space whose root is ``root``."""
    return Path(root) / DATA_DIR


def data_made(root: str, dirs: Sequence[str]) -> nu.Nu:
    """The data dir of the space at ``root`` made, with ``dirs`` in it, where missing. A Command.

    Args:
        root: The space's root, absolute.
        dirs: The dirs the assembly keeps, relative to the data dir.
    """
    data = data_dir(root)
    return MakeDirs(DISK, str(data), *(str(data / d) for d in dirs))


def meta_file(root: str | os.PathLike[str]) -> Path:
    return data_dir(root) / META_FILE


def is_space(root: str | os.PathLike[str]) -> bool:
    """Whether ``root`` is a space: its data dir holds ``meta.json``."""
    return meta_file(root).is_file()


def read_meta(root: str | os.PathLike[str]) -> Meta | None:
    """``meta.json`` of the space at ``root``, or None when there is none.

    Raises:
        Refused: The file is there but does not read as a meta.
    """
    file = meta_file(root)
    try:
        raw = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
        init = data.get("init", False)
        if not isinstance(init, bool):
            raise TypeError(init)
        return Meta(assembly=str(data["assembly"]), made_at=str(data["made_at"]), init=init)
    except (ValueError, KeyError, TypeError, AttributeError):
        msg = f"{file} does not read as a space's meta; fix or remove it"
        raise Refused(msg) from None


def meta_text(meta: Meta) -> str:
    """``meta`` as ``meta.json`` holds it."""
    return json.dumps(asdict(meta)) + "\n"


def write_meta(root: str | os.PathLike[str], meta: Meta) -> None:
    """Write ``meta.json`` of the space at ``root`` whole: a reader never sees half of it.

    Plain Python, for a caller outside a term. A term writes through
    :class:`MetaRef`.
    """
    REAL.write_whole(str(meta_file(root)), meta_text(meta))


def init_done(root: str) -> bool:
    """Whether the space at ``root`` says its assembly's init ran: ``"init": true`` in its meta.

    Raises:
        Refused: The file is there but does not read as a meta.
    """
    meta = read_meta(root)
    return meta is not None and meta.init


#: ``InitDone(root)``: :func:`init_done` as a query, read when the term runs.
InitDone = nu.host(init_done)


class MetaRef(nu.Ref):
    """The Ref naming ``meta.json`` of the space at ``root``: read as the :class:`Meta`, written whole.

    The root rides in the payload, a constant like ``nu.StdioRef``'s
    stream name. Writes go through the disk backend bound on the Context
    (:mod:`.disk`), the real file system otherwise.

    Args:
        root: The space's root, absolute.

    Yields:
        The :class:`Meta`, or None when there is no ``meta.json``.

    Raises:
        Refused: (when read) The file is there but does not read as a meta.
    """

    def __init__(self, root: str) -> None:
        super().__init__()
        self._payload = {"root": root}

    @property
    def root(self) -> str:
        """The space's root."""
        return cast("str", self._payload["root"])

    def read(self) -> Meta | None:
        """The meta now."""
        return read_meta(self.root)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        def thunk(rt: Runtime) -> Meta | None:
            return self.read()

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        async def athunk(rt: Runtime) -> Meta | None:
            return self.read()

        return athunk

    def _write(self, rt: Runtime, value: Meta, nid: int) -> None:
        """``value`` written as the whole file."""
        disk_of(rt.ctx).write_whole(str(meta_file(self.root)), meta_text(value))

    async def _awrite(self, rt: Runtime, value: Meta, nid: int) -> None:
        """Async sibling of :meth:`_write`: a small file, sync work."""
        self._write(rt, value, nid)


def stamped(meta: Meta | None, root: str, assembly: str) -> Meta | None:
    """The meta to write marking ``root`` as ``assembly``'s: a new one when there is none, else None.

    Raises:
        Refused: Another assembly made the space.
    """
    if meta is None:
        return Meta(assembly=assembly, made_at=datetime.now(UTC).isoformat(timespec="seconds"))
    if meta.assembly != assembly:
        msg = (
            f"{root} is a space of the {meta.assembly!r} assembly, not {assembly!r}."
            f" Open it with {meta.assembly!r}"
        )
        raise Refused(msg)
    return None


class Stamp(nu.Command):
    """The space marked as ``assembly``'s: its ``meta.json`` written when there is none.

    Args:
        ref: The space's :class:`MetaRef`.
        assembly: The assembly's name, eg ``"local"``.

    Raises:
        Refused: Another assembly made the space, or its meta does not read.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, ref: MetaRef, assembly: str) -> None:
        super().__init__(ref)
        self._payload = {**self._payload, "assembly": assembly}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = cast("MetaRef", self._children[0])
        assembly = cast("str", self._payload["assembly"])

        def thunk(rt: Runtime) -> None:
            meta = stamped(ref.read(), ref.root, assembly)
            if meta is not None:
                ref._write(rt, meta, rt.program.children[nid][0])

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = cast("MetaRef", self._children[0])
        assembly = cast("str", self._payload["assembly"])

        async def athunk(rt: Runtime) -> None:
            meta = stamped(ref.read(), ref.root, assembly)
            if meta is not None:
                await ref._awrite(rt, meta, rt.program.children[nid][0])

        return athunk


def with_init(meta: Meta | None, root: str, init: bool) -> Meta:
    """``meta`` with ``init`` set.

    Raises:
        Refused: There is no meta.
    """
    if meta is None:
        msg = f"no space at {root} to set init on"
        raise Refused(msg)
    return replace(meta, init=init)


class SetInit(nu.Command):
    """``init`` set in the space's ``meta.json``, the file written whole.

    Args:
        ref: The space's :class:`MetaRef`.
        init: The flag. True once the assembly's init ran to its end.

    Raises:
        Refused: There is no meta, or it does not read.
    """

    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, ref: MetaRef, init: bool = True) -> None:
        super().__init__(ref)
        self._payload = {**self._payload, "init": init}

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = cast("MetaRef", self._children[0])
        init = bool(self._payload["init"])

        def thunk(rt: Runtime) -> None:
            meta = with_init(ref.read(), ref.root, init)
            ref._write(rt, meta, rt.program.children[nid][0])

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        ref = cast("MetaRef", self._children[0])
        init = bool(self._payload["init"])

        async def athunk(rt: Runtime) -> None:
            meta = with_init(ref.read(), ref.root, init)
            await ref._awrite(rt, meta, rt.program.children[nid][0])

        return athunk


def find_space(start: str | os.PathLike[str]) -> Path | None:
    """The nearest space at or above ``start``, as ``git`` finds a repository. None when there is none."""
    here = Path(start).expanduser().resolve()
    return next((d for d in (here, *here.parents) if is_space(d)), None)


def resolve_root(path: str | os.PathLike[str] | None) -> tuple[str, bool]:
    """The space's root, absolute, and whether it is a throwaway one.

    None names a throwaway root in the temp dir: the assembly makes it and
    removes it at the end. Anything else is expanded and resolved.
    """
    if path is None:
        return str(Path(tempfile.gettempdir()) / f"nuspace-{uuid.uuid4().hex[:8]}"), True
    return str(Path(path).expanduser().resolve()), False
