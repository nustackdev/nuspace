"""Devices: ways into the space, each with its own stores. A device calls ops like anyone.

- :mod:`.web`: the browser: the server, its tabs and panes in its own
  stores, the shell's feeds, nav, and the session env.
"""

from . import web


__all__ = ["web"]
