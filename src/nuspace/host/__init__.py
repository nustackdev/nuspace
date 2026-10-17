"""Layer three: the host composes the system.

- :mod:`.space`: :func:`open_space`, the whole system in one term, and
  :func:`init_space`, a space made without running it.
- :mod:`.presets`: :func:`serve`, :func:`headless` and :func:`with_plane`, the
  named ways to open one.

The registry it opens with is :mod:`nuspace.ext`. The ``nuspace`` command is
:mod:`nuspace._cli`, on top of the presets.
"""

from .presets import headless, serve, with_plane
from .space import init_space, open_space


__all__ = ["headless", "init_space", "open_space", "serve", "with_plane"]
