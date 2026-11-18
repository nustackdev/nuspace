"""``nuspace.space.local``: the assembly nuspace ships. Files on this machine, one process per component.

A space runs in three layers, each assuming the ones under it: infra
(the notification server), the kernel, and the devices (web). The
drivers never check what they run on; each entry point checks it once,
at its start, and refuses saying what to start first.

Its entry points, each a term: building it touches nothing,
running it does the work.

- :func:`run`: infra in this process, the kernel and web as two more,
  watched over (:mod:`.supervise`). What ``nuspace run`` does.
- :func:`infra`: what the space runs on, the notification server, in this
  process, under its own lock, for as long as it runs.
- :func:`kernel`: the kernel's driver in this process, under its own
  lock. Needs infra up.
- :func:`web`: web's driver in this process, under its own lock. Needs
  the kernel running.
- :func:`open`: the stores bound around a body of ops, no driver, no
  lock. Needs nothing running.
- :func:`init`: a space made and every component's init run, nothing run
  after. Every other entry point refuses a space not initialized.

Where everything lives on disk is :mod:`.layout`, how the stores are bound
:mod:`.binding`.
"""

from .access import open
from .drivers import infra, kernel, web
from .opening import init
from .supervise import run


__all__ = ["infra", "init", "kernel", "open", "run", "web"]
