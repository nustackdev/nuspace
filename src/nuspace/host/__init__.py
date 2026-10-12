"""Layer three: the host composes the system.

- :mod:`.space`: :func:`open_space`, the whole system in one term.
- :mod:`.presets`: :func:`serve` and :func:`headless`, the named ways to
  open one.

The registry it opens with is :mod:`nuspace.ext`. The ``nuspace`` command is
:mod:`nuspace._cli`, on top of the presets.
"""

from .presets import headless, serve
from .space import open_space


__all__ = ["headless", "open_space", "serve"]
