"""The host: opening a space.

- :mod:`.stores`: the core stores, which root lives in which file, and the
  init terms that make their fixed containers.
"""

from .stores import SPACE_STORE, STATE_STORE, init_live, init_space, init_state


__all__ = ["SPACE_STORE", "STATE_STORE", "init_live", "init_space", "init_state"]
