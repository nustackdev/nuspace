"""The registry: what a space can make and what its runs can be plugged into.

An :class:`Extension` is a bundle of Planes, Cells, content kinds and
env factories. A
package ships one through the ``nuspace.extensions`` entry point group; the
host passes its own straight to :func:`~nuspace.host.open_space`.
:func:`space_registry` is what a space opens with: the host's, then the
installed.

An installed extension's Planes and Cells are named ``<package>.<name>``,
the package being its entry point's name: ``nudemos.movies``,
``nuverse.slider``. That is what a plane or a cell made from one records as
``made_by``, and what ``nuspace run --with`` takes; a cell keeps the short
name as its own. Two packages may share a short name without a clash. What
the host passes directly keeps its names as given.
:func:`registered_name` is the name a spec object registers under, for code
holding the package's own spec rather than the registry's.

Names are unique per kind. On a clash the explicit entry wins, then the
first discovered one, and every entry dropped is reported as a
:class:`RegistryWarning`.
"""

from __future__ import annotations

import functools
import warnings
from dataclasses import dataclass, field, replace
from importlib.metadata import entry_points
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nuspace.content import Content
    from nuspace.system.kernel import EnvFactory

    from .specs import Cell, Plane


__all__ = [
    "GROUP",
    "Extension",
    "Registry",
    "RegistryWarning",
    "discover",
    "qualified",
    "registered_name",
    "short_name",
    "space_registry",
]


#: The entry point group extensions register under.
GROUP = "nuspace.extensions"


class RegistryWarning(UserWarning):
    """An extension could not be loaded, or one of its entries lost a name clash."""


@dataclass(frozen=True)
class Extension:
    """Planes, Cells, content kinds and env factories, registered together.

    Args:
        planes: What ``+`` can create.
        cells: What ``/`` can insert.
        envs: Env factories by name, see :mod:`nuspace.system.kernel.envs`.
        name: Where it came from, for warnings. An entry point's name when
            discovered and left empty.
        contents: The content kinds, :class:`~nuspace.content.Content`
            subclasses, what cells keep items of and search finds. Last, so
            an extension spelled positionally before kinds still reads.
    """

    planes: tuple[Plane, ...] = ()
    cells: tuple[Cell, ...] = ()
    envs: Mapping[str, EnvFactory] = field(default_factory=dict)
    name: str = ""
    contents: tuple[type[Content], ...] = ()


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


def qualified(ext: Extension, package: str) -> Extension:
    """``ext`` with its Planes and Cells named ``<package>.<name>``, as an installed one registers."""
    return replace(
        ext,
        planes=tuple(replace(p, name=f"{package}.{p.name}") for p in ext.planes),
        cells=tuple(replace(s, name=f"{package}.{s.name}") for s in ext.cells),
    )


def short_name(name: str) -> str:
    """A registered name without its package: ``nuverse.slider`` as ``slider``."""
    return name.rpartition(".")[2]


@functools.cache
def _registered(group: str = GROUP) -> dict[int, tuple[object, str]]:
    """Every installed spec object by id, with the name it registers under. Loaded once."""
    found: dict[int, tuple[object, str]] = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RegistryWarning)
        for point in entry_points(group=group):
            ext = _load(point)
            for spec in (*ext.planes, *ext.cells) if ext is not None else ():
                found.setdefault(id(spec), (spec, f"{point.name}.{spec.name}"))
    return found


def registered_name(spec: Plane | Cell) -> str:
    """The name ``spec`` registers under: ``<package>.<name>`` when an installed package adds it.

    Its own name otherwise: the host's, an unregistered child, or a spec the
    registry already named.
    """
    hit = _registered().get(id(spec))
    return hit[1] if hit is not None and hit[0] is spec else spec.name


def discover(group: str = GROUP) -> list[Extension]:
    """Every extension installed under ``group``, in entry point order, its Planes qualified.

    Each entry point loads to an :class:`Extension`, or to a callable
    returning one. One that fails to load, or is neither, is skipped with a
    :class:`RegistryWarning`. Its Planes are named after the entry point,
    see :func:`qualified`.
    """
    found = [(point.name, _load(point)) for point in entry_points(group=group)]
    return [qualified(ext, package) for package, ext in found if ext is not None]


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
        cells: By name.
        contents: Content kinds by their importable name, in registration order.
        envs: Env factories by name.
    """

    planes: Mapping[str, Plane] = field(default_factory=dict)
    cells: Mapping[str, Cell] = field(default_factory=dict)
    contents: Mapping[str, type[Content]] = field(default_factory=dict)
    envs: Mapping[str, EnvFactory] = field(default_factory=dict)

    @classmethod
    def merge(cls, extensions: Iterable[Extension]) -> Registry:
        """Extensions in precedence order merged: the first to name a thing keeps it."""
        exts = list(extensions)
        # Each kind by its importable name, as nuspace.content.kind_name spells it.
        kinds = ((f"{k.__module__}.{k.__qualname__}", e.name, k) for e in exts for k in e.contents)
        return cls(
            planes=_merge("plane", ((p.name, e.name, p) for e in exts for p in e.planes)),
            cells=_merge("cell", ((s.name, e.name, s) for e in exts for s in e.cells)),
            contents=_merge("content", kinds),
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


def space_registry(
    *,
    planes: Sequence[Plane] = (),
    cells: Sequence[Cell] = (),
    contents: Sequence[type[Content]] = (),
    envs: Mapping[str, EnvFactory] | None = None,
    extensions: Sequence[Extension] | None = None,
    discover: bool = True,
) -> Registry:
    """What a space registers: the loose arguments, then ``extensions``, then installed ones.

    Args:
        planes: Planes passed directly, ahead of everything.
        cells: Cells passed directly.
        contents: Content kinds passed directly.
        envs: Env factories passed directly.
        extensions: Explicit extensions, after the loose arguments.
        discover: Also load the ``nuspace.extensions`` entry points.
    """
    loose = Extension(
        tuple(planes),
        tuple(cells),
        dict(envs or {}),
        name="open_space",
        contents=tuple(contents),
    )
    return Registry.build([loose, *(extensions or ())], discovered=None if discover else [])
