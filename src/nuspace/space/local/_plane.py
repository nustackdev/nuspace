"""The plane a space opens on: the newest made from a spec, made from it when there is none.

What ``local.web(plane=...)`` and ``local.run(plane=...)`` open the tab on,
and what ``nuspace run --with`` names. Ops on the bound stores, the same
body an ``open`` would run, so it works wherever the stores are bound.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space
from nuspace.specs import add_plane, plane_spec, registered_name


if TYPE_CHECKING:
    from nuspace.specs import PlaneSpec


__all__ = ["found", "plane_of"]


def found(spec: PlaneSpec | str) -> PlaneSpec:
    """``spec``, or the spec registered under that name.

    Raises:
        Missing: No plane spec of that name.
    """
    return plane_spec(spec) if isinstance(spec, str) else spec


def plane_of(spec: PlaneSpec, plane: nu.Ref) -> nu.Nu:
    """``plane`` set to the spec's newest plane, made from the spec first when there is none.

    The newest is the last of ``Space.indexes.spec_planes[spec].ids``, one
    seek. Removed, or never made, a new one is made (``specs.add_plane``,
    its own commits) and becomes the newest. So the next open with the same
    spec finds the same plane, with what was done to it.
    """
    newest = Space.indexes.spec_planes[registered_name(spec)].ids.last(default="")
    gone = nuspace.plane.exists(nu.Str(plane)).not_()
    return plane.set(atomic(newest)) >> nu.IfDo(atomic(gone), add_plane(spec, into=plane))
