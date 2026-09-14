"""nuspace.web.chat -- the agent sidebar, browser side.

The ref and the driver that works it, together:

- :mod:`.ref`    -- ``ChatRef``, one conversation and the box that starts one.
- :mod:`.driver` -- ``chat_driver``, one ``ReactForever`` arm per interaction.

What an event means in kv is :mod:`nuspace.agent.ops`, in the store-side
package of the same name. The loop those writes wake is
:mod:`nuspace.agent.runner`, and neither side imports the other.
"""

from __future__ import annotations

from .driver import ARMS, chat_driver
from .ref import ChatRef


__all__ = ["ARMS", "ChatRef", "chat_driver"]
