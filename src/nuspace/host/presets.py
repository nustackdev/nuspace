"""Presets: the named ways to open a space, each one :func:`~.space.open_space` call.

- :func:`serve`: with the web device. What ``nuspace run`` does.
- :func:`headless`: no device served, for scripts and servers.
- :func:`with_plane`: open on the plane of a spec, made from the spec when
  the space has none. What ``nuspace run --with`` does.

The command line maps one command or flag to one preset and adds nothing of
its own. Anything else :func:`~.space.open_space` takes passes through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace.ops.brackets import atomic
from nuspace.shapes import Space
from nuspace.specs import add_plane, plane_spec, registered_name

from .interactions import Browse
from .space import open_space


if TYPE_CHECKING:
    import os

    from nuspace.specs import PlaneSpec


__all__ = ["headless", "serve", "with_plane"]


def serve(path: str | os.PathLike[str] | None = None, **kwargs: object) -> nu.With:
    """The space at ``path`` served in a browser: :func:`open_space` with the web device.

    Raises:
        Refused: As :func:`open_space`.
    """
    return open_space(path, devices=("web",), **kwargs)


def headless(path: str | os.PathLike[str] | None = None, **kwargs: object) -> nu.With:
    """The space at ``path`` with no device served: the kernel and the system planes run.

    Every device's stores still open, without their drivers, so a program
    writing a device's rows (``add_plane`` of a spec with ``web=``) works.

    Raises:
        Refused: As :func:`open_space`.
    """
    return open_space(path, devices=(), **kwargs)


def _plane_of(spec: PlaneSpec, plane: nu.Ref) -> nu.Nu:
    """``plane`` set to the spec's newest plane, made from the spec first when there is none.

    The newest is the last of ``Space.indexes.spec_planes[spec].ids``, one
    seek. Removed, or never made, a new one is made (``specs.add_plane``,
    its own commits) and becomes the newest.
    """
    newest = Space.indexes.spec_planes[registered_name(spec)].ids.last(default="")
    gone = nuspace.plane.exists(nu.Str(plane)).not_()
    return plane.set(atomic(newest)) >> nu.IfDo(atomic(gone), add_plane(spec, into=plane))


def with_plane(
    path: str | os.PathLike[str] | None,
    spec: PlaneSpec | str,
    *,
    web: bool = True,
    host: str = "127.0.0.1",
    port: int = 8080,
    open_browser: bool = True,
    **kwargs: object,
) -> nu.With:
    """The space at ``path`` opened on the plane of ``spec``, served or headless.

    The plane is the newest one made from ``spec``
    (``Space.indexes.spec_planes``), made from the spec when there is none
    or it is removed. So the next open with the same spec finds the same
    plane, with what was done to it. Served, the browser opens on it rather
    than on home. Headless, a spec with ``web=`` still gets its web row: the
    web device's stores open without its driver.

    Args:
        path: The space's root, as :func:`open_space`.
        spec: The plane spec, or its registered name (``nudemos.movies``).
        web: Serve the web device; False is headless.
        host: The interface the web device binds.
        port: The port it binds.
        open_browser: Open a tab on the plane once the server is up.
        **kwargs: The rest of :func:`open_space`'s options.

    Raises:
        Missing: No plane spec of that name (at build).
        Refused: As :func:`open_space`.
    """
    found = plane_spec(spec) if isinstance(spec, str) else spec

    def opened(plane: nu.ObjectRef) -> nu.Nu:
        steps = [_plane_of(found, plane)]
        if web and open_browser:
            # The web device's own url, so the tab opens on the same encoded path a link would.
            from nuspace.web.interactions import Href

            url = nu.Str(f"http://{host}:{port}") + nu.Str(Href(plane, {}))
            steps.append(Browse(url, host, port))
        return nu.Sequential(*steps, nu.Park())

    body = nu.let("", opened)
    if not web:
        return open_space(path, devices=(), body=body, **kwargs)
    return open_space(
        path, devices=("web",), host=host, port=port, open_browser=False, body=body, **kwargs
    )
