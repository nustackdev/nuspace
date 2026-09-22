"""The agent a chat runs: it answers by drawing.

A chat is two Planes. One runs, and the Cell on it is this package. One
draws, and what is on it is whatever the agent has put there. Every turn the
agent appends Cells to the Plane that draws: one or more presenting what it
did, and one that is how the person answers next. The reply box is not chrome
any more, it is a Cell the model wrote, so it can just as well be three
buttons, a form, a slider, or a diff with approve and reject on it.

What stays uniform is the **record**. Whatever the person does through
whatever the agent drew lands in the conversation as an ordinary
``{role, text}`` message, and that list is what wakes the agent for the next
turn. Cells are presentation; the conversation is the truth.

That is natural here and awkward anywhere else, because a Cell's program is
Nu: what the model generates is a live program bound to the store rather than
a dead render of a payload. It also persists as an ordinary Cell, so a person
can open what the agent made and edit it.

Four modules and a prompt::

    conversation    the turn loop: what is outstanding, ask, append, record
    cc              Claude Code. one session for as long as the chat
    llm             a served model over the OpenAI wire. one call per turn
    steps           what the agent is doing, written down as it happens
    prompt          what the model reads, as markdown on disk

The two endpoints are the same five lines to the loop and nothing else in
common, and they are deliberately not abstracted over each other: see
:mod:`nuspace.agent.llm` for why.

**This package is where the behaviour lives, not the template.** A chat's
talking Cell holds ten lines that call :func:`converse`, so installing a
newer nuspace upgrades every chat already in the store. Templates are seeds
and a seed has no migration; for a prompt that gets tuned daily, seeding is
the wrong shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nustd.kv
from nuspace.agent import conversation, prompt, steps
from nuspace.agent.cc import claude_code
from nuspace.agent.llm import served_model
from nuspace.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu


__all__ = [
    "claude_code",
    "conversation",
    "converse",
    "prompt",
    "served_model",
    "steps",
]


def converse(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    root: type[Space] = Space,
    talk: Callable[..., nu.Nu] | None = None,
) -> nu.Nu:
    """The whole term a chat's talking Cell runs.

    Answer whatever is outstanding, then wait for more, forever, with the
    endpoint held open around all of it.

    Args:
        plane_id: the Plane the chat runs on. The Cell's own ``plane``.
        cell_id: the Cell on it that talks and holds the conversation. The
            Cell's own ``cell``.
        ui_plane_id: the Plane the agent draws its turns onto. The other half
            of the pair a chat is, and the one the person is looking at.
        root: the Space shape class. It decides the store the agent writes to
            and the surface it is shown, so a subclassed Space gets a prompt
            about itself.
        talk: the endpoint, ``endpoint(turns, *, system)``. ``None`` means
            Claude Code with its defaults, which is what a chat made by
            pressing ``+`` gets. Pass
            :func:`~nuspace.agent.llm.served_model` or
            :func:`~nuspace.agent.cc.claude_code` with arguments of your own
            for anything else.

    Returns:
        A Flow that never ends on its own.

    Notes:
        - The bracket over the store is here rather than in the template,
          because a program owns its own atomicity and this *is* the
          program. Nothing brackets it on the way in: the host cannot see
          inside a program it evaluates.
        - The endpoint goes up once, outside the wait, so a session lasts as
          long as the chat rather than as long as a turn.
    """
    endpoint = claude_code() if talk is None else talk

    def turns(ask: Callable[..., nu.Nu]) -> nu.Nu:
        return conversation.answering(
            plane_id, cell_id, ui_plane_id=ui_plane_id, ask=ask, root=root
        )

    return nustd.kv.auto_flow_atomic(
        endpoint(turns, system=prompt.system_prompt(root=root)), scope=root
    )
