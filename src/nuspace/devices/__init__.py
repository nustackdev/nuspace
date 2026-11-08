"""Devices: each owns an external resource and makes it bindable. Never runs cells.

- :mod:`.web`: the ws server, browser connections in the store, the shell's
  feeds, and the session env.
"""

from . import web


__all__ = ["web"]
