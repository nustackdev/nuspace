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
import os
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from nuspace.errors import Refused


__all__ = [
    "DATA_DIR",
    "META_FILE",
    "Meta",
    "data_dir",
    "find_space",
    "is_space",
    "read_meta",
    "resolve_root",
    "set_init",
    "stamp",
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


def write_meta(root: str | os.PathLike[str], meta: Meta) -> None:
    """Write ``meta.json`` of the space at ``root`` whole: a reader never sees half of it."""
    file = meta_file(root)
    file.parent.mkdir(parents=True, exist_ok=True)
    part = file.with_name(f".{META_FILE}.{os.getpid()}")
    part.write_text(json.dumps(asdict(meta)) + "\n", encoding="utf-8")
    part.replace(file)


def stamp(root: str | os.PathLike[str], assembly: str) -> Meta:
    """The space at ``root`` marked as ``assembly``'s: its meta, written now when there is none.

    Raises:
        Refused: Another assembly made the space, or its meta does not read.
    """
    meta = read_meta(root)
    if meta is None:
        meta = Meta(assembly=assembly, made_at=datetime.now(UTC).isoformat(timespec="seconds"))
        write_meta(root, meta)
    elif meta.assembly != assembly:
        msg = (
            f"{root} is a space of the {meta.assembly!r} assembly, not {assembly!r}."
            f" Open it with {meta.assembly!r}"
        )
        raise Refused(msg)
    return meta


def set_init(root: str | os.PathLike[str], init: bool = True) -> Meta:
    """``init`` set in the meta of the space at ``root``, the file written whole. The new meta.

    Raises:
        Refused: There is no meta, or it does not read.
    """
    meta = read_meta(root)
    if meta is None:
        msg = f"no space at {root} to set init on"
        raise Refused(msg)
    meta = replace(meta, init=init)
    write_meta(root, meta)
    return meta


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
