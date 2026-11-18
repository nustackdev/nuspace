"""``nuspace.space``: running a space. A namespaced runtime, not ops (unlike ``nuspace.<object>.<verb>``).

- :mod:`.blocks`: the parts an assembly is built from: the lock, the
  notifier, navigators, the workers' context, ``meta.json``, root resolving.
- :mod:`.local`: the assembly nuspace ships, ``from nuspace.space import local``.

Re-exports nothing: write the assembly in front.
"""

from . import blocks, local


__all__ = ["blocks", "local"]
