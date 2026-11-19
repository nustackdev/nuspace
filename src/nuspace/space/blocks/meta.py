"""What every assembly shares about a space on disk: the data dir, ``meta.json``, read and written as nu terms.

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

:class:`Meta` is the value, :class:`MetaForm` its Form: a term yielding a
``Meta`` reads ``m.assembly`` in the tree, and makes its next value with
``m.with_init(flag)``. Everything here is nu ops over that form: the file
is read through an fs mount the assembly binds (``nustd.fs``), parsed and
written with ``nustd.json``, stamped with ``nustd.datetime``, and each
refusal is a ``Raise`` of a formatted ``Str``. :func:`meta_in`,
:func:`stamp`, :func:`set_init`, :func:`init_done` each take the file on
that mount, a ``FileRef``, so the block never knows the assembly's tag.
The command line reads it the same way, over a mount of its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import nu
import nustd.json
from nuspace.errors import Refused
from nustd.datetime import datetime, timezone

from .required import refused


if TYPE_CHECKING:
    import os

    from nustd.fs import FileRef


__all__ = [
    "DATA_DIR",
    "META_FILE",
    "Meta",
    "MetaForm",
    "init_done",
    "meta_in",
    "not_other",
    "ran",
    "resolve_root",
    "said",
    "set_init",
    "stamp",
]


#: The directory inside a space's root holding its data.
DATA_DIR = ".nuspace"

#: The one file every assembly keeps in :data:`DATA_DIR`.
META_FILE = "meta.json"


@dataclass(frozen=True)
class Meta:
    """What ``meta.json`` says. The plain value; :class:`MetaForm` is its Form.

    Attributes:
        assembly: The name of the assembly that made the space, eg ``"local"``.
        made_at: When ``meta.json`` was written, an ISO 8601 time in UTC.
        init: Whether the assembly's init ran to its end on the space.
    """

    assembly: str
    made_at: str
    init: bool = False


class MetaForm(nu.Form, nu.TypedNu[Meta]):
    """A :class:`Meta` as a Form: its fields read in the tree, its next value made there.

    Build one with :meth:`of`, :meth:`made` or :meth:`loads`, or wrap a
    term yielding a ``Meta``: ``MetaForm(ref).assembly``.
    """

    # --- constructors --------------------------------------------------------

    @classmethod
    def of(cls, assembly: nu.StrArg, made_at: nu.StrArg, init: nu.BoolArg = False) -> MetaForm:
        """A meta from its three fields, built on every run."""
        return MetaForm(nu.Literal(factory=Meta, assembly=assembly, made_at=made_at, init=init))

    @classmethod
    def made(cls, assembly: nu.StrArg) -> MetaForm:
        """A new meta marking a space as ``assembly``'s, made now: UTC, to the second, init not run."""
        now = datetime.now(timezone.utc()).replace(microsecond=0)
        return cls.of(assembly, now.isoformat())

    @classmethod
    def loads(cls, text: nu.StrArg) -> MetaForm:
        """The meta ``meta.json``'s ``text`` holds, or None for ``null``. No field is type checked: it is our file.

        Raises:
            ValueError: (at run) ``text`` is no JSON.
            KeyError: (at run) A field is missing.
            TypeError: (at run) The JSON is no object.
        """

        def built(data: nu.ObjectRef) -> nu.Nu:
            fields = nu.Dict(data)
            meta = cls.of(
                nu.GetItem(data, "assembly"),
                nu.GetItem(data, "made_at"),
                fields.get_item("init", False),
            )
            return nu.If(nu.Is(data, None), nu.Literal(None), meta)

        return MetaForm(nu.let(nustd.json.loads(text), built))

    # --- fields --------------------------------------------------------------

    @property
    def assembly(self) -> nu.Str:
        """The name of the assembly that made the space."""
        return nu.Str(nu.GetAttr(self, "assembly"))

    @property
    def made_at(self) -> nu.Str:
        """When the space was marked, ISO 8601 in UTC."""
        return nu.Str(nu.GetAttr(self, "made_at"))

    @property
    def init(self) -> nu.Bool:
        """Whether the assembly's init ran to its end."""
        return nu.Bool(nu.GetAttr(self, "init"))

    # --- next values ---------------------------------------------------------

    def with_init(self, flag: nu.BoolArg) -> MetaForm:
        """This meta with ``init`` set to ``flag``."""
        return MetaForm.of(self.assembly, self.made_at, flag)

    def as_dict(self) -> nu.Dict:
        """What ``meta.json`` holds of this meta: its three fields."""
        return nu.Dict.of(assembly=self.assembly, made_at=self.made_at, init=self.init)


def said(template: str, **fields: object) -> nu.Str:
    """``template`` with its ``{name}`` fields filled at run: a refusal's text, eg ``said("{root} is gone", root=r)``."""
    return nu.Str(template).format_map(nu.Dict.of(**fields))


def meta_in(file: FileRef) -> MetaForm:
    """``meta.json`` read through its mount: the :class:`Meta`, or None when there is none. A query.

    A missing file, or one holding ``null``, is no meta. Anything else that
    does not read as one raises once, inside, and is refused here.

    Args:
        file: ``meta.json`` on the assembly's mount of the data dir.

    Raises:
        Refused: (at run) The file is there but does not read as a meta.
    """
    unreadable = said("{file} does not read as a space's meta; fix or remove it", file=file.where())
    loaded = nu.TryCatch(
        MetaForm.loads(file.read_text(default="null")),
        errors=(ValueError, KeyError, TypeError),
        catch=nu.Raise(unreadable, exc_cls=Refused),
    )
    return MetaForm(loaded)


def ran(meta: nu.Nu) -> nu.Bool:
    """Whether ``meta``, a meta or None, says its assembly's init ran. ``meta`` is read twice: hand it a ref."""
    return nu.Bool(nu.And(nu.Not(nu.Is(meta, None)), MetaForm(meta).init))


def not_other(meta: nu.Nu, root: nu.StrArg, assembly: str) -> nu.Nu:
    """The space at ``root`` refused when ``meta``, a meta or None, is another assembly's. A step.

    Raises:
        Refused: (at run) Another assembly made the space.
    """
    other = MetaForm(meta).assembly
    why = said(
        "{root} is a space of the {other!r} assembly, not {assembly!r}. Open it with {other!r}",
        root=root,
        other=other,
        assembly=assembly,
    )
    return refused(nu.And(nu.Not(nu.Is(meta, None)), other != assembly), why)


def dumped(meta: MetaForm) -> nu.Str:
    """``meta`` as the text ``meta.json`` holds: one JSON line."""
    return nustd.json.dumps(meta.as_dict()) + "\n"


def stamp(file: FileRef, root: nu.StrArg, assembly: str) -> nu.Nu:
    """The space marked as ``assembly``'s: its ``meta.json`` written when there is none. A step.

    Args:
        file: ``meta.json`` on the assembly's mount of the data dir.
        root: The space's root, absolute, as a refusal names it.
        assembly: The assembly's name, eg ``"local"``.

    Raises:
        Refused: (at run) Another assembly made the space, or its meta does not read.
    """
    return nu.let(
        meta_in(file),
        lambda meta: nu.IfDo(
            nu.Is(meta, None),
            nu.let(MetaForm.made(assembly), lambda made: file.write_text(dumped(MetaForm(made)))),
            not_other(meta, root, assembly),
        ),
    )


def set_init(file: FileRef, root: nu.StrArg, init: bool = True) -> nu.Nu:
    """``init`` set in the space's ``meta.json``, the file written whole. A step.

    Args:
        file: ``meta.json`` on the assembly's mount of the data dir.
        root: The space's root, absolute, as a refusal names it.
        init: The flag. True once the assembly's init ran to its end.

    Raises:
        Refused: (at run) There is no meta, or it does not read.
    """
    none = said("no space at {root} to set init on", root=root)
    return nu.let(
        meta_in(file),
        lambda meta: (
            refused(nu.Is(meta, None), none)
            >> file.write_text(dumped(MetaForm(meta).with_init(init)))
        ),
    )


def init_done(file: FileRef) -> nu.Bool:
    """Whether the space says its assembly's init ran: ``"init": true`` in its meta. A query.

    Args:
        file: ``meta.json`` on a mount of the data dir.

    Raises:
        Refused: (at run) The file is there but does not read as a meta.
    """
    return nu.Bool(nu.let(meta_in(file), lambda meta: ran(meta)))


def resolve_root(path: str | os.PathLike[str] | nu.Nu) -> str | nu.Nu:
    """The root an entry point runs on: a term as it is (eg a temp dir's mount), a path absolute, ``~`` expanded.

    Nothing on disk is looked at: the mount over the root resolves it when
    it opens, and says where it is with ``where()``.
    """
    if isinstance(path, nu.Nu):
        return path
    return str(Path(path).expanduser().absolute())
