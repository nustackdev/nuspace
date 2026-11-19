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

A term reads and writes ``meta.json`` through an fs mount the assembly
binds over the data dir (``nustd.fs``), parsed and written with
``nustd.json``: :func:`meta_in`, :func:`stamp`, :func:`set_init`,
:func:`init_done` each take the file on that mount, a ``FileRef``, so the
block never knows the assembly's tag. Plain Python outside a term, eg the
command line finding a space before anything runs, reads it with
:func:`read_meta`.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.json
from nuspace.errors import Refused

from .guarded import refused


if TYPE_CHECKING:
    import os

    from nustd.fs import FileRef


__all__ = [
    "DATA_DIR",
    "META_FILE",
    "Meta",
    "data_dir",
    "find_space",
    "init_done",
    "is_space",
    "meta_in",
    "other_refusal",
    "read_meta",
    "resolve_root",
    "set_init",
    "stamp",
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


def meta_file(root: str | os.PathLike[str]) -> Path:
    return data_dir(root) / META_FILE


def is_space(root: str | os.PathLike[str]) -> bool:
    """Whether ``root`` is a space: its data dir holds ``meta.json``."""
    return meta_file(root).is_file()


def unreadable(root: str | os.PathLike[str]) -> str:
    """What a refusal says of a ``meta.json`` that does not read."""
    return f"{meta_file(root)} does not read as a space's meta; fix or remove it"


def meta_of(data: object, root: str) -> Meta | None:
    """The :class:`Meta` in ``data``, ``meta.json`` as loaded, or None when there is none (``null``).

    Raises:
        Refused: ``data`` does not read as a meta.
    """
    if data is None:
        return None
    try:
        init = data.get("init", False)  # type: ignore[attr-defined]
        if not isinstance(init, bool):
            raise TypeError(init)
        return Meta(assembly=str(data["assembly"]), made_at=str(data["made_at"]), init=init)  # type: ignore[index]
    except (ValueError, KeyError, TypeError, AttributeError):
        raise Refused(unreadable(root)) from None


def read_meta(root: str | os.PathLike[str]) -> Meta | None:
    """``meta.json`` of the space at ``root``, or None when there is none. Plain Python, outside a term.

    Raises:
        Refused: The file is there but does not read as a meta.
    """
    try:
        raw = meta_file(root).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        raise Refused(unreadable(root)) from None
    if data is None:
        raise Refused(unreadable(root))
    return meta_of(data, str(root))


#: ``MetaOf(data, root)``: :func:`meta_of` as a query.
MetaOf = nu.host(meta_of)


def meta_in(file: FileRef, root: str) -> nu.Nu:
    """``meta.json`` read through its mount: the :class:`Meta`, or None when there is none. A query.

    Args:
        file: ``meta.json`` on the assembly's mount of the data dir.
        root: The space's root, absolute, as a refusal names it.

    Raises:
        Refused: (at run) The file is there but does not read as a meta.
    """
    loaded = nu.TryCatch(
        nustd.json.loads(file.read_text(default="null")),
        errors=ValueError,
        catch=nu.Raise(unreadable(root), exc_cls=Refused),
    )
    return MetaOf(loaded, root)


def other_refusal(meta: Meta | None, root: str, assembly: str) -> str:
    """Why ``root`` is refused for being another assembly's space, or ``""``."""
    if meta is not None and meta.assembly != assembly:
        return (
            f"{root} is a space of the {meta.assembly!r} assembly, not {assembly!r}."
            f" Open it with {meta.assembly!r}"
        )
    return ""


#: ``OtherRefusal(meta, root, assembly)``: :func:`other_refusal` as a query.
OtherRefusal = nu.host(other_refusal)


def made(assembly: str) -> dict[str, object]:
    """A new meta marking a space as ``assembly``'s, as ``meta.json`` holds it, made now."""
    return asdict(Meta(assembly=assembly, made_at=datetime.now(UTC).isoformat(timespec="seconds")))


def with_init(meta: Meta | None, root: str, init: bool) -> dict[str, object]:
    """``meta`` with ``init`` set, as ``meta.json`` holds it.

    Raises:
        Refused: There is no meta.
    """
    if meta is None:
        msg = f"no space at {root} to set init on"
        raise Refused(msg)
    return asdict(replace(meta, init=init))


def is_init(meta: Meta | None) -> bool:
    """Whether ``meta`` says its assembly's init ran."""
    return meta is not None and meta.init


#: ``Made(assembly)``, ``WithInit(meta, root, init)``, ``IsInit(meta)``: the helpers above as queries.
Made = nu.host(made)
WithInit = nu.host(with_init)
IsInit = nu.host(is_init)


def dumped(data: object) -> nu.Nu:
    """``data`` as the text ``meta.json`` holds: one JSON line."""
    return nustd.json.dumps(data) + "\n"


def stamp(file: FileRef, root: str, assembly: str) -> nu.Nu:
    """The space marked as ``assembly``'s: its ``meta.json`` written when there is none.

    Args:
        file: ``meta.json`` on the assembly's mount of the data dir.
        root: The space's root, absolute, as a refusal names it.
        assembly: The assembly's name, eg ``"local"``.

    Raises:
        Refused: (at run) Another assembly made the space, or its meta does not read.
    """
    return nu.let(
        meta_in(file, root),
        lambda meta: nu.IfDo(
            nu.Is(meta, None),
            file.write_text(dumped(Made(assembly))),
            refused(OtherRefusal(meta, root, assembly)),
        ),
    )


def set_init(file: FileRef, root: str, init: bool = True) -> nu.Nu:
    """``init`` set in the space's ``meta.json``, the file written whole.

    Args:
        file: ``meta.json`` on the assembly's mount of the data dir.
        root: The space's root, absolute, as a refusal names it.
        init: The flag. True once the assembly's init ran to its end.

    Raises:
        Refused: (at run) There is no meta, or it does not read.
    """
    return file.write_text(dumped(WithInit(meta_in(file, root), root, init)))


def init_done(file: FileRef, root: str) -> nu.Nu:
    """Whether the space says its assembly's init ran: ``"init": true`` in its meta. A query.

    Args:
        file: ``meta.json`` on a mount of the data dir.
        root: The space's root, absolute, as a refusal names it.

    Raises:
        Refused: (at run) The file is there but does not read as a meta.
    """
    return IsInit(meta_in(file, root))


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
