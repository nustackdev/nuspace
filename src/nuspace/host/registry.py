"""The registry: what a space can make and what its runs can be plugged into.

An :class:`Extension` is a bundle of Planes, snippets and env factories. A
package ships one through the ``nuspace.extensions`` entry point group, the
same way nuverse does and a third party would; the host passes its own
straight to :func:`~nuspace.host.space.open_space`.

Names are unique per kind. On a clash the explicit entry wins, then the
first discovered one, and every entry dropped is reported as a
:class:`RegistryWarning`.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field, replace
from importlib.metadata import entry_points
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from nuspace.ops import Plane, Snippet
    from nuspace.system.kernel import EnvFactory


__all__ = ["GROUP", "Extension", "Registry", "RegistryWarning", "discover"]


#: The entry point group extensions register under.
GROUP = "nuspace.extensions"


class RegistryWarning(UserWarning):
    """An extension could not be loaded, or one of its entries lost a name clash."""


@dataclass(frozen=True)
class Extension:
    """Planes, snippets and env factories, registered together.

    Args:
        planes: What ``+`` can create.
        snippets: What ``/`` can insert.
        envs: Env factories by name, see :mod:`nuspace.system.kernel.envs`.
        name: Where it came from, for warnings. An entry point's name when
            discovered and left empty.
    """

    planes: tuple[Plane, ...] = ()
    snippets: tuple[Snippet, ...] = ()
    envs: Mapping[str, EnvFactory] = field(default_factory=dict)
    name: str = ""


def _load(point: object) -> Extension | None:
    """One entry point as an extension, or None with a warning when it is not one."""
    try:
        loaded = point.load()
        ext = loaded if isinstance(loaded, Extension) else loaded()
    except Exception as exc:  # A broken extension must not stop the space
        warnings.warn(
            f"Extension {point.name!r} failed to load: {exc!r}", RegistryWarning, stacklevel=3
        )
        return None
    if not isinstance(ext, Extension):
        warnings.warn(
            f"Extension {point.name!r} is not an Extension: {type(ext).__name__}",
            RegistryWarning,
            stacklevel=3,
        )
        return None
    return ext if ext.name else replace(ext, name=point.name)


def discover(group: str = GROUP) -> list[Extension]:
    """Every extension installed under ``group``, in entry point order.

    Each entry point loads to an :class:`Extension`, or to a callable
    returning one. One that fails to load, or is neither, is skipped with a
    :class:`RegistryWarning`.
    """
    found = [_load(point) for point in entry_points(group=group)]
    return [ext for ext in found if ext is not None]


def _merge(kind: str, entries: Iterable[tuple[str, str, object]]) -> dict[str, object]:
    """``(name, source, entry)`` in precedence order, first per name kept."""
    kept: dict[str, object] = {}
    source: dict[str, str] = {}
    for name, where, entry in entries:
        if name in kept:
            warnings.warn(
                f"{kind.capitalize()} {name!r} from {where or 'unnamed'} ignored:"
                f" {source[name] or 'unnamed'} registered it first",
                RegistryWarning,
                stacklevel=4,
            )
            continue
        kept[name] = entry
        source[name] = where
    return kept


@dataclass(frozen=True)
class Registry:
    """Everything a space registered, merged, one entry per name and kind.

    Args:
        planes: By name, in registration order.
        snippets: By name.
        envs: Env factories by name.
    """

    planes: Mapping[str, Plane] = field(default_factory=dict)
    snippets: Mapping[str, Snippet] = field(default_factory=dict)
    envs: Mapping[str, EnvFactory] = field(default_factory=dict)

    @classmethod
    def merge(cls, extensions: Iterable[Extension]) -> Registry:
        """Extensions in precedence order merged: the first to name a thing keeps it."""
        exts = list(extensions)
        return cls(
            planes=_merge("plane", ((p.name, e.name, p) for e in exts for p in e.planes)),
            snippets=_merge("snippet", ((s.name, e.name, s) for e in exts for s in e.snippets)),
            envs=_merge("env", ((n, e.name, f) for e in exts for n, f in e.envs.items())),
        )

    @classmethod
    def build(
        cls, explicit: Iterable[Extension] = (), *, discovered: Iterable[Extension] | None = None
    ) -> Registry:
        """The explicit extensions, then the discovered ones.

        Args:
            explicit: What the host passed, first wins among them too.
            discovered: Installed extensions. None runs :func:`discover`.
        """
        found = discover() if discovered is None else list(discovered)
        return cls.merge([*explicit, *found])
