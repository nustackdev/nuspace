"""The devices a host can open a space with, by name: what each brings to an open.

A device is a way into the space with its own stores. To the host it is
three things: the stores it opens beside the core ones (and every worker
binds), the planes it seeds where missing, and its driver, built only when
the space is served, since that pulls in the device's server.

Every open opens every device's stores (:func:`device_stores`), served or
headless, so a program writing a device's rows (``add_plane`` of a spec
with ``web=``) works either way. Only the devices an open names seed their
planes and run their drivers.

- ``web``: the browser. Stores Web and Conn (Conn made fresh at every
  open), the home, settings and search planes, the server and nav.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nuspace.errors import Missing


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    import nu
    from nuspace.kernel import EnvFactory
    from nuspace.shapes import Store
    from nuspace.specs import Registry


__all__ = ["DEVICES", "Device", "device", "device_stores"]


@dataclass(frozen=True)
class Device:
    """One device as the host opens it.

    Attributes:
        name: What ``open_space(devices=...)`` calls it.
        stores: Its stores, opened after the core ones.
        seed: Builds the bare term making its planes where missing, run
            before the drivers. It brackets itself.
        serve: Builds its driver and the env factories it registers,
            ``serve(registry=, **options) -> (term, envs)``. Imports the
            device's server, so it is called only when the space is served.
    """

    name: str
    stores: tuple[Store, ...]
    seed: Callable[[], nu.Nu]
    serve: Callable[..., tuple[nu.Nu, Mapping[str, EnvFactory]]]


def _web() -> Device:
    """The web device. Its stores and planes import no server; :func:`serve` does, when called."""
    from nuspace.web.planes import ensure
    from nuspace.web.stores import CONN_STORE, WEB_STORE

    def serve(*, registry: Registry, **options: object) -> tuple[nu.Nu, Mapping[str, EnvFactory]]:
        from nuspace.web.device import serve_web

        return serve_web(registry=registry, **options)

    return Device("web", (WEB_STORE, CONN_STORE), ensure, serve)


#: Every device a host knows, by name, built when asked for.
DEVICES: dict[str, Callable[[], Device]] = {"web": _web}


def device(name: str) -> Device:
    """The device named ``name``.

    Raises:
        Missing: No device of that name.
    """
    made = DEVICES.get(name)
    if made is None:
        msg = f"no device {name!r}; known: {', '.join(DEVICES)}"
        raise Missing(msg)
    return made()


def device_stores() -> tuple[Store, ...]:
    """Every known device's stores, in :data:`DEVICES` order: what every open opens beside the core."""
    return tuple(s for made in DEVICES.values() for s in made().stores)
