"""What is installed under the ``nuspace.extensions`` entry points, one entry per package.

``nuspace verse`` lists it and ``nuspace run --with`` picks a Plane out of
it. A package is its entry point's name, and its Planes are
``<package>.<name>``, as a space registers them
(:func:`~nuspace.ext.qualified`). A bare name is a Plane of
:data:`DEFAULT_PACKAGE`, the one nuspace ships with.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

import rich_click as click

from nuspace.ext.registry import GROUP, _load, qualified

from ._meta import version_of


if TYPE_CHECKING:
    from nuspace.ext import Extension, PlaneSpec


__all__ = ["DEFAULT_PACKAGE", "Installed", "installed", "resolve"]


DEFAULT_PACKAGE = "nuverse"
"""The package a bare plane name is looked up in: ``jobs`` is ``nuverse.jobs``."""


@dataclass(frozen=True)
class Installed:
    """One package registering an extension.

    Args:
        name: The entry point's name, the ``pkg`` of ``pkg.plane``.
        version: The installed version of the distribution it ships in.
        extension: What it registers, its Planes' names short. None when it
            failed to load.
        error: Why it failed to load, empty when it did not.
    """

    name: str
    version: str
    extension: Extension | None
    error: str = ""


def installed(group: str = GROUP) -> list[Installed]:
    """Every package registering under ``group``, in entry point order."""
    found: list[Installed] = []
    for point in entry_points(group=group):
        version = point.dist.version if point.dist is not None else version_of(point.name)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ext = _load(point)
        error = "" if ext is not None else str(caught[-1].message) if caught else "failed to load"
        found.append(Installed(point.name, version, ext, error))
    return found


def resolve(spec: str, packages: list[Installed] | None = None) -> PlaneSpec:
    """``pkg.plane`` as the Plane it names, qualified as a space registers it.

    A bare name, with no dot, is a Plane of :data:`DEFAULT_PACKAGE`.

    Raises:
        click.ClickException: ``spec`` is not ``pkg.plane`` or a bare name, or
            no installed package adds it.
    """
    packages = installed() if packages is None else packages
    bare = "." not in spec
    full = f"{DEFAULT_PACKAGE}.{spec}" if bare else spec
    pkg, _, name = full.partition(".")
    hits = [
        plane
        for p in packages
        if p.extension is not None and p.name == pkg
        for plane in qualified(p.extension, p.name).planes
        if plane.name == full
    ]
    if pkg and name and hits:
        return hits[0]
    if bare:
        raise click.ClickException(_not_in_default(spec, packages))
    raise click.ClickException(
        f"No plane {spec!r} installed. Name it pkg.plane, see: nuspace verse"
    )


def _not_in_default(spec: str, packages: list[Installed]) -> str:
    """Why bare ``spec`` names no Plane: what :data:`DEFAULT_PACKAGE` has instead, if anything."""
    ext = next((p.extension for p in packages if p.name == DEFAULT_PACKAGE and p.extension), None)
    head = f"No plane {spec!r} in {DEFAULT_PACKAGE}, where a bare name is looked up."
    tail = "Name another package's as pkg.plane, see: nuspace verse"
    if ext is None:
        return f"{head} {DEFAULT_PACKAGE} is not installed or failed to load. {tail}"
    names = ", ".join(plane.name for plane in ext.planes) or "none"
    return f"{head} Its planes: {names}. {tail}"
