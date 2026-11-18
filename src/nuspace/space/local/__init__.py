"""``nuspace.space.local``: the assembly nuspace ships. One process runs the space, for now.

- :func:`open_space`: the whole open as one term; :func:`make_space`: one
  made and seeded, nothing run.
- :func:`serve`, :func:`headless`, :func:`with_plane`: the named ways to open one.
"""

from ._single import make_space, open_space
from .presets import headless, serve, with_plane


__all__ = ["headless", "make_space", "open_space", "serve", "with_plane"]
