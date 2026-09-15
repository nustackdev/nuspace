"""The conversation: what was said, by whom, in order.

Separate from ``Agent`` on purpose, and the separation is the whole idea.

``Agent`` is a *run*: one task, its status, and nuagent's working memory --
the model's raw replies, the extracted source, the observation the host wrote
after evaluating it. That is machinery. Nobody is talking in there.

``Chat`` is what was *said*. And for this agent, saying something is an
**action**, not a side channel: nuagent's only output is a Nu term, so the
model speaks by emitting a program that appends here. Asked how many pages a
space has, it does not answer in prose -- it writes a program that counts them
and appends the count. Exactly the same primitive as every other thing it does,
which means a cron job, an app or a person at a REPL can post here too, and the
sidebar cannot tell the difference. There is nothing to tell.

That also means the model's reply *text* is not shown anywhere. What it types
around the fence is reasoning, and reasoning is not an answer. If it wants to
be heard it appends. :mod:`nuspace.agent.prompt` says so in as many words.

One conversation, matching the one run ``Agent`` holds. When a space grows
more than one agent this becomes a ``ShapesDictRef`` keyed by thread id and
nothing else about it moves.

A message is a plain ``{role, text}`` dict rather than a Shape, so appending is
one call the model can write without looking anything up::

    Space.chat.messages.append(nu.Dict.of(role="agent", text="there are 3 pages"))
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["ROLES", "ROLE_AGENT", "ROLE_SYSTEM", "ROLE_USER", "Chat"]


#: A person typed it in the sidebar.
ROLE_USER = "user"
#: The agent wrote it, by appending, in a program it emitted.
ROLE_AGENT = "agent"
#: The host wrote it about the run itself -- budget gone, loop crashed. Never
#: about the work, which is the agent's to report.
ROLE_SYSTEM = "system"

#: Every role the surface renders. Anything else falls back to ``system``, so
#: a program inventing a role is legible rather than invisible.
ROLES = (ROLE_USER, ROLE_AGENT, ROLE_SYSTEM)


class Chat(nu.Shape):
    """One conversation. A list of ``{role, text}``, oldest first."""

    messages = nustd.kv.ListRef.slot(dict)
