"""Connection: one live client of a device, eg a browser tab."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["Connection"]


class Connection(nu.Shape):
    """What a device publishes about one client. Written by the device only.

    ``route`` is where the client is, which is what nav watches to decide
    what runs for it. Services on workers read it through the store, since
    the device itself lives in the host.
    """

    route = nustd.kv.StrRef.slot()
    opened = nustd.kv.FloatRef.slot()
