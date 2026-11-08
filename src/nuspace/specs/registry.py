"""The registry: what a space can make and what its runs can be plugged into.

An :class:`Extension` is a bundle of specs, one tuple per extension point
(:class:`~.specs.PlaneSpec`, :class:`~.specs.CellSpec`,
:class:`~.specs.ContentSpec`), and env factories. A package ships one
through the ``nuspace.extensions`` entry point group, and that is the only
way anything registers: what registers is what installed packages'
extensions add. A host picks which packages a space takes
(:func:`space_registry`), never adds specs of its own; its own env
factories are the one thing it passes, being callables, not specs.

Everything installed is named ``<package>.<name>``, the package being its
entry point's name: ``nudemos.movies`` and ``nuverse.slider`` for a Plane
and a Cell, ``nuverse.Text`` for a content kind. That is what a plane or a
cell made from one records as ``made_by``, what ``nuspace run --with``
takes, and what the store keys a kind's items by; a cell keeps the short
name as its own. Two packages may share a short name without a clash.

The installed extensions are browsed the same way in any process, the
host's or a worker's: loaded from the entry points once, then cached. So a
name alone is enough to find what it names, with no registry object handed
over:

- :func:`content_spec`: a content kind's registered name to its spec, and
  through it to the kind; :func:`content_specs`, every one, for a reader
  that offers the kinds, eg a search form, built where it runs;
- :func:`kind_name`: a content kind's class to the name it registers under;
- :func:`registered_name`: the name a Plane or Cell spec object registers
  under, for code holding the package's own spec rather than the registry's.

Names are unique per kind. On a clash the first discovered one wins, a
host's env over an installed one, and every entry dropped is reported as a
:class:`RegistryWarning`.
"""

from __future__ import annotations

import functools
import warnings
from dataclasses import dataclass, field, replace
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    from nuspace.content import Content
    from nuspace.system.kernel import EnvFactory

    from .specs import CellSpec, ContentSpec, PlaneSpec


__all__ = [
    "GROUP",
    "Extension",
    "Registry",
    "RegistryWarning",
    "content_spec",
    "content_specs",
    "discover",
    "kind_name",
    "qualified",
    "registered_name",
    "short_name",
    "space_registry",
]


#: The entry point group extensions register under.
GROUP = "nuspace.extensions"

#: Where a host's own env factories come from, for warnings.
HOST = "open_space"


class RegistryWarning(UserWarning):
    """An extension could not be loaded, or one of its entries lost a name clash."""


@dataclass(frozen=True)
class Extension:
    """What one installed package adds to a space: specs, and env factories.

    Args:
        planes: What ``+`` can create.
        cells: What ``/`` can insert.
        contents: The content kinds cells keep items of and search finds.
        envs: Env factories by name, see :mod:`nuspace.system.kernel.envs`.
    """

    planes: tuple[PlaneSpec, ...] = ()
    cells: tuple[CellSpec, ...] = ()
    contents: tuple[ContentSpec, ...] = ()
    envs: Mapping[str, EnvFactory] = field(default_factory=dict)


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
    return ext


def qualified(ext: Extension, package: str) -> Extension:
    """``ext`` with its Planes and Cells named ``<package>.<name>``, as an installed one registers.

    Its content specs stay as they are: a kind's name is its class's, and
    the registry puts the package in front.
    """
    return replace(
        ext,
        planes=tuple(replace(p, name=f"{package}.{p.name}") for p in ext.planes),
        cells=tuple(replace(s, name=f"{package}.{s.name}") for s in ext.cells),
    )


def short_name(name: str) -> str:
    """A registered name without its package: ``nuverse.slider`` as ``slider``."""
    return name.rpartition(".")[2]


def _loaded(group: str) -> dict[str, Extension]:
    """Every installed extension by package, as its package wrote it, in entry point order."""
    found: dict[str, Extension] = {}
    for point in entry_points(group=group):
        ext = _load(point)
        if ext is None:
            continue
        if point.name in found:
            warnings.warn(
                f"Extension {point.name!r} is installed twice: the first is kept",
                RegistryWarning,
                stacklevel=3,
            )
            continue
        found[point.name] = ext
    return found


def discover(group: str = GROUP) -> dict[str, Extension]:
    """Every extension installed under ``group``, by package, in entry point order, qualified.

    Each entry point loads to an :class:`Extension`, or to a callable
    returning one. One that fails to load, or is neither, is skipped with a
    :class:`RegistryWarning`. Its Planes and Cells are named after the
    entry point, see :func:`qualified`.
    """
    return {package: qualified(ext, package) for package, ext in _loaded(group).items()}


def _merge(kind: str, entries: Iterable[tuple[str, str, object]]) -> dict[str, Any]:
    """``(name, source, entry)`` in precedence order, first per name kept."""
    kept: dict[str, object] = {}
    source: dict[str, str] = {}
    for name, where, entry in entries:
        if name in kept:
            warnings.warn(
                f"{kind.capitalize()} {name!r} from {where} ignored: {source[name]} registered it first",
                RegistryWarning,
                stacklevel=4,
            )
            continue
        kept[name] = entry
        source[name] = where
    return kept


def _contents(extensions: Iterable[tuple[str, Extension]]) -> dict[str, ContentSpec]:
    """The content specs by registered name, first kept, one name per kind class.

    A kind is keyed in the store by one name, so a class a second spec lists
    again, under any name, is dropped with a warning.
    """
    kept = _merge("content", ((f"{p}.{c.name}", p, c) for p, e in extensions for c in e.contents))
    named: dict[type, str] = {}
    for name, spec in list(kept.items()):
        if spec.kind in named:
            warnings.warn(
                f"Content {name!r} ignored: its kind is registered as {named[spec.kind]!r}",
                RegistryWarning,
                stacklevel=3,
            )
            del kept[name]
            continue
        named[spec.kind] = name
    return kept


@dataclass(frozen=True)
class Registry:
    """Everything a space registered, merged, one entry per name and kind.

    Args:
        planes: By registered name, in registration order.
        cells: By registered name.
        contents: Content specs by registered name, ``nuverse.Text``, in
            registration order.
        envs: Env factories by name.
    """

    planes: Mapping[str, PlaneSpec] = field(default_factory=dict)
    cells: Mapping[str, CellSpec] = field(default_factory=dict)
    contents: Mapping[str, ContentSpec] = field(default_factory=dict)
    envs: Mapping[str, EnvFactory] = field(default_factory=dict)

    @classmethod
    def merge(
        cls, extensions: Mapping[str, Extension], *, envs: Mapping[str, EnvFactory] | None = None
    ) -> Registry:
        """Installed extensions by package, qualified, merged in order: the first to name a thing keeps it.

        Args:
            extensions: Package to its extension, as :func:`discover` gives them.
            envs: The host's own env factories, ahead of every package's.
        """
        exts = list(extensions.items())
        host = ((n, HOST, f) for n, f in (envs or {}).items())
        return cls(
            planes=_merge("plane", ((p.name, pkg, p) for pkg, e in exts for p in e.planes)),
            cells=_merge("cell", ((s.name, pkg, s) for pkg, e in exts for s in e.cells)),
            contents=_contents(exts),
            envs=_merge(
                "env", [*host, *((n, pkg, f) for pkg, e in exts for n, f in e.envs.items())]
            ),
        )


def space_registry(
    *,
    extensions: Sequence[str] | None = None,
    envs: Mapping[str, EnvFactory] | None = None,
) -> Registry:
    """What a space registers: the installed packages' extensions, and the host's env factories.

    Args:
        extensions: The packages to take, by entry point name, in any order:
            their precedence is the entry points'. None takes every
            installed one, ``()`` none.
        envs: Env factories of the host's own, ahead of every package's.

    Raises:
        LookupError: ``extensions`` names a package not installed.
    """
    found = discover()
    if extensions is not None:
        missing = [name for name in extensions if name not in found]
        if missing:
            msg = f"No extension installed as {', '.join(map(repr, missing))}: see nuspace verse"
            raise LookupError(msg)
        found = {package: ext for package, ext in found.items() if package in extensions}
    return Registry.merge(found, envs=envs)


# --- Installed, by name, in any process ----------------------------------------------


@dataclass(frozen=True)
class _Installed:
    """Every installed extension, merged, and the names its packages' own spec objects register under."""

    registry: Registry
    names: Mapping[int, tuple[object, str]]
    kinds: Mapping[type, str]


@functools.cache
def _installed(group: str = GROUP) -> _Installed:
    """Every installed extension, loaded once per process, quietly: a space's open reports what fails."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RegistryWarning)
        raw = _loaded(group)
        reg = Registry.merge({package: qualified(ext, package) for package, ext in raw.items()})
    names: dict[int, tuple[object, str]] = {}
    for package, ext in raw.items():
        for spec in (*ext.planes, *ext.cells):
            names.setdefault(id(spec), (spec, f"{package}.{spec.name}"))
    kinds = {spec.kind: name for name, spec in reg.contents.items()}
    return _Installed(reg, names, kinds)


def content_spec(name: str) -> ContentSpec:
    """The installed content spec registered as ``name``, eg ``nuverse.Text``. Its kind is ``.kind``.

    Raises:
        LookupError: No installed package adds a kind of that name.
    """
    found = _installed().registry.contents.get(name)
    if found is None:
        msg = f"No content kind {name!r} installed"
        raise LookupError(msg)
    return found


def content_specs() -> Mapping[str, ContentSpec]:
    """Every installed content spec by registered name, in registration order."""
    return _installed().registry.contents


def kind_name(kind: type[Content[Any]]) -> str:
    """The name ``kind`` registers under, ``<package>.<kind.name>``: what the store keys its items by.

    From the installed extension listing that kind, so any process names it
    alike, headless ones too.

    Raises:
        LookupError: No installed package's extension lists ``kind``.
    """
    found = _installed().kinds.get(kind)
    if found is None:
        msg = f"Content kind {kind.__qualname__} is not installed: no package's extension lists it"
        raise LookupError(msg)
    return found


def registered_name(spec: PlaneSpec | CellSpec) -> str:
    """The name ``spec`` registers under: ``<package>.<name>`` when an installed package adds it.

    Its own name otherwise: an unregistered child, or a spec the registry
    already named.
    """
    hit = _installed().names.get(id(spec))
    return hit[1] if hit is not None and hit[0] is spec else spec.name
