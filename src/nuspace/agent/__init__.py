"""nuspace.agent -- the nuagent loop, as a slot on the space.

Store side, laid out like :mod:`nuspace.apps` next door: what the store holds,
what an interaction means in kv, and what the host process runs.

- :mod:`.shapes` -- ``Agent``, nuagent's session slots plus the submission.
- :mod:`.ops`    -- write + read primitives. A submit is a kv write.
- :mod:`.prompt` -- the system prompt: nuagent's sections, the space as world.
- :mod:`.model`  -- the model endpoint, and the run transcript flattened for it.
- :mod:`.runner` -- the resident loop. One arm: nonce moved, run to completion.

What the agent *says* is not here: that is :mod:`nuspace.chat`, on the agent's
own surface, and it gets there because the model emitted a program that
appended to it. The browser half of both is :mod:`nuspace.web.chat`.

**This barrel is deliberately thin.** ``core.shapes`` imports ``Agent`` to
build ``Space``, and importing this package is what that costs, so only
``shapes`` and ``ops`` are pulled in -- the two modules that import ``nu``,
``_root`` and nothing else. ``model``, ``prompt`` and ``runner`` reach into ``nuagent`` and
``nuspace.web``; :mod:`nuspace.web.space` imports it by name, once, where there is
no cycle left to close.
"""

from __future__ import annotations

from . import ops
from .shapes import (
    DEFAULT_MAX_TURNS,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_STOPPED,
    Agent,
)


__all__ = [
    "DEFAULT_MAX_TURNS",
    "STATUS_DONE",
    "STATUS_FAILED",
    "STATUS_IDLE",
    "STATUS_RUNNING",
    "STATUS_STOPPED",
    "Agent",
    "ops",
]
