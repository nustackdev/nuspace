"""One chat, live: answer whatever is outstanding, then wait for more.

The loop a chat's talking Cell runs, and the only thing in this package that
knows what a turn is. It reads the conversation out of the Cell's own state,
because a Cell's state is where a Cell's state goes and because the Plane
that draws the chat is ``nav`` and is down whenever nobody is looking at it.

**There is no submit to watch for.** A chat is made at ``manual`` and the
first message flips its Plane to ``boot``, so a Cell coming up *is* the
signal. Everything after that arrives as a change on the container the
conversation lives in.

**The question is read twice and both reads earn their place.** The first
covers the gap between a run ending and this subscribing, where a message
would otherwise wait for the next one; the second is the wait itself, which
ends on the message that makes an answer owed and sits through every other
write. Steps share that container, so most wakes are the agent's own
narration rather than anything said; the guard is what makes that free.

**One run per outstanding question, and nuagent's working memory lasts
exactly that long.** :class:`~nuagent.MemSession` holds the model's raw
replies and the host's observations, which is machinery, and it is thrown
away with the run. What the person reads is what the model *drew* and what it
*appended*, and those are different substances that live in the store.

The endpoint is not here. It is brought up once, around this whole loop, so a
Claude Code session lasts as long as the chat rather than as long as a turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nuagent

import nu
from nuspace import ops
from nuspace.agent import steps
from nuspace.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["CRASHED", "MAX_TURNS", "OPENING", "SILENT", "answering"]


#: Turns one message gets. Small on purpose: a question that has not been
#: answered in this many is usually one that needed splitting, and a model
#: editing a live Space is cheaper to re-ask than to let wander.
MAX_TURNS = 8

#: What the host says when a run ended without the model saying anything. The
#: host speaks here and nowhere else, and it earns its place twice: silence
#: reads as a broken space rather than as an unfinished job, and an answered
#: question is what stops this asking the same one again.
SILENT = "That run ended without an answer. Ask again, or ask for less."

#: Same, for the loop itself dying. The model's own mistakes never reach
#: this: a module that will not construct is fed back to it and the run
#: carries on.
CRASHED = "The run crashed and stopped: "

#: What the first user message of a run says before the ids and the
#: conversation. The ask itself is the last thing in that conversation, so
#: there is nothing to restate.
OPENING = "Somebody is talking to you in a chat. Answer the last thing they said."


def answering(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    ask: Callable[..., nu.Nu],
    root: type[Space] = Space,
) -> nu.Nu:
    """The whole life of a chat, as one term.

    Args:
        plane_id: the Plane the chat runs on.
        cell_id: the Cell on it that talks and holds the conversation.
        ui_plane_id: the Plane the agent draws its turns onto.
        ask: what one turn calls to reach the model, nuagent's ``chat=``.
            Called with ``messages=`` and yields a dict with ``text`` in it.
            Handed in rather than chosen here, because which model a chat
            talks to is the endpoint's business and the loop is the same
            either way.
        root: the Space shape class.

    Returns:
        A ``ForeverDo``: answer what is owed, wait until something is owed,
        repeat. It never ends on its own.
    """

    def owed() -> nu.Nu:
        """Whether the chat is waiting on a reply. Fresh at each call site."""
        return ops.chat.unanswered(plane_id, cell_id, root=root)

    return nu.ForeverDo(
        nu.IfDo(owed(), _run(plane_id, cell_id, ui_plane_id=ui_plane_id, ask=ask, root=root))
        >> nu.IfDo(
            nu.Not(owed()),
            nu.ReactWhile(
                ops.chat.changed(plane_id, cell_id, root=root), nu.Not(owed()), nu.Noop()
            ),
        )
    )


def _opening(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    ui_plane_id: nu.StrArg,
    *,
    root: type[Space],
) -> nu.Nu:
    """A run's first user message: where this chat is, and what was said.

    The three ids ride in the message rather than in the system prompt
    because the prompt is a python string built once and the ids are terms
    the running tree resolves. The labels are the words the prompt uses for
    them, so a model copying one off this message is copying the thing the
    prose told it to look for.

    The conversation is restated at the top of every run even when the
    endpoint kept its session. A session is lost to any restart and the
    conversation is not, so the run that comes back after one has to be told
    everything, and a run that did not is told it twice for the price of a
    page of tokens.
    """
    return nu.Dict.of(
        role="user",
        content=nu.Str(OPENING)
        + nu.Str("\n\nchat plane: ")
        + nu.ToStr(plane_id)
        + nu.Str("\nchat cell: ")
        + nu.ToStr(cell_id)
        + nu.Str("\nui plane: ")
        + nu.ToStr(ui_plane_id)
        + nu.Str("\n\nWhat has been said, oldest first:\n\n")
        + nu.ToStr(nu.Repr(ops.chat.messages_of(plane_id, cell_id, root=root))),
    )


def _run(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    ask: Callable[..., nu.Nu],
    root: type[Space],
) -> nu.Nu:
    """One nuagent loop over the conversation as it stands, and what closes it.

    Two dict fabrics, and the split is the whole of what the model can reach.
    The session is tagged, so nothing the model writes touches the run's own
    memory. The untagged one is where ``Run.done`` lives and where any
    ``nustd.mem`` the model invents lands, out of the way of the store. Both
    are provided per run rather than per chat, so a run always starts on an
    empty working memory however long the chat has been up.

    ``state`` is what the model is shown after each of its programs ran. The
    Cells already on the ui plane are in it deliberately: a model that cannot
    see what it drew draws it again.
    """

    def owed() -> nu.Nu:
        """Whether the chat is still waiting. Fresh at each call site."""
        return ops.chat.unanswered(plane_id, cell_id, root=root)

    loop = nuagent.agent(
        session=nuagent.MemSession,
        chat=ask,
        state=nu.Dict.of(
            planes=ops.plane_ids(root=root),
            drawn=ops.cell_ids(ui_plane_id, root=root),
            said=ops.chat.messages_of(plane_id, cell_id, root=root),
        ),
        max_turns=MAX_TURNS,
        start=steps.started(plane_id, cell_id, root=root)
        >> nuagent.MemSession.messages.set(
            nu.List.of(_opening(plane_id, cell_id, ui_plane_id, root=root))
        ),
        report=nu.IfDo(
            owed(),
            ops.chat.say(plane_id, cell_id, ops.chat.ROLE_SYSTEM, SILENT, root=root)
            >> steps.stalled(plane_id, cell_id, root=root),
            steps.ended(plane_id, cell_id, root=root),
        ),
        # Quiet. The turn prints on the worker's own stdout, which nobody is
        # reading: a Cell is in a process of its own and what it has to say
        # reaches a person through the chat, or through the error on its row
        # when it could not say anything at all.
        echo=False,
    )
    return nu.With(
        nu.Provide(dict, {}, tag=nuagent.MemSession),
        nu.Provide(dict, {}),
        body=nu.TryCatch(
            loop,
            catch=ops.chat.say(
                plane_id,
                cell_id,
                ops.chat.ROLE_SYSTEM,
                nu.Str(CRASHED) + nu.ToStr(nu.AttrRef("error")),
                root=root,
            )
            >> steps.crashed(plane_id, cell_id, nu.AttrRef("error"), root=root),
        ),
    )
