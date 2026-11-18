"""``nuspace.space.local``: the assembly nuspace ships. Files on this machine, one process per driver.

Its entry points, each a ``nu.With`` term: building it touches nothing,
running it does the work.

- :func:`run`: the kernel and web as two processes, watched over
  (:mod:`.supervise`). What ``nuspace run`` does.
- :func:`kernel`, :func:`web`: one driver in this process, under its own lock.
- :func:`open`: the stores bound around a body of ops, no driver, no lock.
- :func:`init`: a space made and seeded, nothing run.

Where everything lives on disk is :mod:`.layout`, how the stores are bound
:mod:`.binding`.
"""

from ._drivers import kernel, web
from ._open import init, open
from .supervise import run


__all__ = ["init", "kernel", "open", "run", "web"]
