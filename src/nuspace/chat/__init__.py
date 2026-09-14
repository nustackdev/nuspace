"""nuspace.chat -- the conversation, as a slot on the space.

- :mod:`.shapes` -- ``Chat``: a list of ``{role, text}``, and the three roles.
- :mod:`.ops`    -- ``say`` and the reads. One write verb, because a
  conversation is a log.

The point of the split from :mod:`nuspace.agent`: that package holds a *run*,
this one holds what was *said*. The agent reaches this one the way it reaches
everything else -- by emitting a program that appends. Saying something is an
action on the space, not a channel beside it.

The browser half is :mod:`nuspace.web.chat`.
"""

from __future__ import annotations

from . import ops
from .shapes import ROLE_AGENT, ROLE_SYSTEM, ROLE_USER, ROLES, Chat


__all__ = ["ROLES", "ROLE_AGENT", "ROLE_SYSTEM", "ROLE_USER", "Chat", "ops"]
