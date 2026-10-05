"""Claude Code, and one conversation for as long as the chat lives.

A space is a thing you run on the machine you are sitting at, so the endpoint
a chat talks to by default is the Claude Code already installed on it rather
than an api key somebody has to find.

**The session is the whole point of this file.** ``nustd.cc.Session`` is a
brace: every prompt inside it is a turn of one conversation, on one ``claude``
process. Opened around the chat's whole loop rather than around a pass, so the
model keeps its own context from one pass of a turn to the next and a prompt
carries only what is new. Without it every call is a cold start, the entire
transcript has to ride in every prompt, and pass eight re-sends seven passes
of code and diagnostics to be told one line.

**The conversation outlives the process.** Its id is minted before the first
prompt and kept in the talking Cell's state, and the brace is opened on that
id. So a Cell that restarts, for a new nuspace, a crash or a reboot, picks the
same conversation back up instead of starting a stranger on it.

So :func:`ask` sends the newest message and nothing before it. That is right
cold as well as warm: the first message of a turn is the opening, which
carries the conversation whole, and every message after it is an observation
about the pass that just ran.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.cc
from nuspace import ops
from nuspace.agent import session as memory


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


__all__ = ["MODEL", "Bot", "ask", "claude_code"]


#: What a chat talks to when nobody says otherwise.
MODEL = "claude-opus-5"


class Bot(nu.Service):
    """The Claude Code endpoint a chat runs against."""

    ask = nustd.cc.PromptRef.method()


def ask(*, messages: nu.Nu) -> nu.Nu:
    """One pass's prompt: the newest message, and nothing before it.

    What one pass calls. It hands over the whole transcript and this
    takes the last of it, because the rest is already in the session.

    Args:
        messages: the working memory's message list, oldest first.

    Returns:
        The prompt interaction, yielding a dict with ``text`` in it.
    """
    newest = nu.Dict(nu.List(messages)[nu.Int(-1)])
    return Bot.ask(prompt=nu.ToStr(newest.get_item(nu.Str("content"), nu.Str(""))))


def claude_code(
    *,
    model: str = MODEL,
    allowed_tools: Sequence[str] = (),
    permission_mode: str = "default",
) -> Callable[..., nu.Nu]:
    """The endpoint a chat runs against: Claude Code, in one conversation.

    Args:
        model: which model to ask.
        allowed_tools: the tools Claude Code may use. Empty on purpose: the
            model's action here is the Nu program it writes, and a model that
            can edit files as well has two ways to change the world and only
            one of them is in the transcript.
        permission_mode: what Claude Code does when something needs
            permission. Nobody is at the terminal to answer, so this only
            matters once tools are allowed.

    Returns:
        A callable ``endpoint(loop, *, system, cell_id)``. ``loop`` is what
        to run once the endpoint is up, as a function of :func:`ask`;
        ``system`` is the system prompt; ``cell_id`` is the Cell the agent
        runs in, whose state keeps the conversation's id. It yields whatever
        ``loop`` yields.

    Notes:
        - The brace is the process's lifetime. It opens on the first prompt
          and stops when the ``With`` exits, so everything the chat will
          ever do has to be inside it.
        - The id is not the process. It is written once, the first time the
          Cell runs, and every later start opens the brace on it again.
        - Reach is by Context rather than by ownership, so a prompt inside a
          nested ``With`` the loop opens still joins the session.
    """

    def endpoint(
        loop: Callable[..., nu.Nu],
        *,
        system: str,
        cell_id: nu.StrArg,
    ) -> nu.Nu:
        return nu.With(
            nustd.cc.bind(
                Bot,
                model=model,
                system_prompt=system,
                allowed_tools=list(allowed_tools),
                permission_mode=permission_mode,
            ),
            body=_minted(cell_id)
            >> nu.let(
                ops.snapshot(memory.sid_of(cell_id)),
                lambda sid: nustd.cc.Session(loop(ask), sid=sid),
            ),
        )

    return endpoint


def _minted(cell_id: nu.StrArg) -> nu.Nu:
    """Give the Cell a conversation id if it has none yet. One short commit.

    Minting is all it takes: the conversation begins under the id on the first
    prompt, so the id is safe to keep before anything has been said, and a Cell
    that dies before then comes back to an id that simply starts it.

    Guarded on the Cell, because a write under a key nobody made makes one.
    """
    return ops.atomic_state(
        nu.IfDo(
            ops.cell_exists(cell_id),
            nu.IfDo(
                nu.Not(memory.sid_of(cell_id).exists()),
                memory.sid_of(cell_id).set(nustd.cc.NewSession()),
            ),
        )
    )
