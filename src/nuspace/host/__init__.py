"""Layer three: the host composes the system.

- :mod:`.space`: :func:`open_space`, the whole system in one term, and
  :func:`init_space`, a space made without running it.
- :mod:`.presets`: :func:`serve`, :func:`headless` and :func:`demo`, the
  named ways to open one.

The registry it opens with is :mod:`nuspace.ext`. The ``nuspace`` command is
:mod:`nuspace._cli`, on top of the presets.
"""

from .presets import demo, headless, serve
from .space import init_space, open_space


__all__ = ["demo", "headless", "init_space", "open_space", "serve"]
