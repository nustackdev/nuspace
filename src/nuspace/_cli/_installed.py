"""What is installed under the ``nuspace.extensions`` entry points, one entry per package.

``nuspace verse`` lists it and ``nuspace run --with`` picks a Plane out of
it. A package is its entry point's name, and its Planes are
``<package>.<name>``, as a space registers them
(:func:`~nuspace.ext.qualified`).
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
    from nuspace.ext import Extension, Plane


__all__ = ["Installed", "installed", "resolve"]


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


def resolve(spec: str, packages: list[Installed] | None = None) -> Plane:
    """``pkg.plane`` as the Plane it names, qualified as a space registers it.

    Raises:
        click.ClickException: ``spec`` is not ``pkg.plane``, or no installed
            package adds it.
    """
    packages = installed() if packages is None else packages
    pkg, dot, name = spec.partition(".")
    hits = [
        plane
        for p in packages
        if p.extension is not None and p.name == pkg
        for plane in qualified(p.extension, p.name).planes
        if plane.name == spec
    ]
    if not (pkg and dot and name and hits):
        raise click.ClickException(
            f"No plane {spec!r} installed. Name it pkg.plane, see: nuspace verse"
        )
    return hits[0]
