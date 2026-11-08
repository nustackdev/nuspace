"""``nuspace.host``: opening a space and running it. Not called from inside a space.

- :mod:`.space`: :func:`open_space`, the whole open as one term (lock,
  format check, fresh device stores, reap, spares, drivers, and at close
  what is live ended), and
  :func:`make_space`, a space made and seeded with nothing run.
- :mod:`.presets`: :func:`serve`, :func:`headless`, :func:`with_plane`.
- :mod:`.stores`: the core stores, their init terms, and the store presets
  every process opens them with, each store on its own channel.
- :mod:`.layout`: where a space keeps its data, how one is found.
- :mod:`.lock`: the host lock. :mod:`.resources`: what an open binds
  around the stores. :mod:`.devices`: the devices a space opens with.

Namespaced, never re-exported at the top. Imports no device server: a
device's is imported when a space is served.
"""

from .layout import DATA_DIR, data_dir, find_space, is_space
from .presets import headless, serve, with_plane
from .space import make_space, open_space
from .stores import CORE, SPACE_STORE, STATE_STORE, init_live, init_space, init_state, navigators


__all__ = [
    "CORE",
    "DATA_DIR",
    "SPACE_STORE",
    "STATE_STORE",
    "data_dir",
    "find_space",
    "headless",
    "init_live",
    "init_space",
    "init_state",
    "is_space",
    "make_space",
    "navigators",
    "open_space",
    "serve",
    "with_plane",
]
