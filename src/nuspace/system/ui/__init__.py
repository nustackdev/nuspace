"""The system ui planes: fixed ids, seeded by the host at open, the owner's after that.

- :mod:`.home`: the plane ``/`` redirects to.
- :mod:`.settings`: the space's own settings.
- :mod:`.search`: searches as planes, and the plane that asks and shows them.

Each is seeded once (:mod:`.seed`). Services, the background planes, live
next door (:mod:`nuspace.system.services`).
"""

from . import home, search, seed, settings


__all__ = ["home", "search", "seed", "settings"]
