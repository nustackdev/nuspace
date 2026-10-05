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
covers the gap between a turn ending and this subscribing, where a message
would otherwise wait for the next one; the second is the wait itself, which
ends on the message that makes an answer owed and sits through every other
write.

**A turn is two cycles and nothing else.** Work, then answer. The work cycle
can stall and the turn still answers: a model that could not do the thing
still owes the person a sentence, and a turn that said nothing is the worst
outcome available to it. Only the answer cycle failing leaves the chat still
owed a reply, and that is the one place the host speaks. What it says is the
account the cycle that stopped wrote about itself, because a person told only
that nothing came back has been told nothing they can do anything with.

The endpoint is not here. It is brought up once, around this whole loop, so a
Claude Code process lasts as long as the Cell runs rather than as long as a
turn, and the conversation it is having outlasts the Cell: its id is kept in
the Cell's state and a restart opens the same one.

Every read here is a snapshot of its own and every write a short commit,
the wait's subscription and its condition included, so a chat that sits
waiting for a week holds nothing open on the store.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.agent import chat, cycles, prompt, trace
from nuspace.agent import session as memory


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["ASK_AGAIN", "CRASHED", "SILENT", "answering", "performing"]


#: What the host says when a turn ended without the model answering and
#: without either cycle having anything to say about why. The host speaks here
#: and nowhere else, and it earns its place twice: silence reads as a broken
#: space rather than as an unfinished job, and an answered question is what
#: stops this asking the same one again.
SILENT = "That turn ended without an answer."

#: And what goes after it, or after the cycle's own account of where it
#: stopped. It is the only part a person can act on, so it is the part that is
#: always there.
ASK_AGAIN = " Ask again, or ask for less."

#: Same, for the loop itself dying. The model's own mistakes never reach this:
#: a module that will not construct is fed back to it and the turn carries on.
CRASHED = "The turn crashed and stopped: "


def answering(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    ask: Callable[..., nu.Nu],
) -> nu.Nu:
    """The whole life of a chat, as one term.

    Args:
        plane_id: the Plane the chat runs on.
        cell_id: the Cell on it that talks and holds the conversation.
        ui_plane_id: the Plane the agent draws its answers onto.
        ask: what one pass calls to reach the model. Called with ``messages=``
            and yields a dict with ``text`` in it. Handed in rather than chosen
            here, because which model a chat talks to is the endpoint's
            business and the loop is the same either way.

    Returns:
        A ``ForeverDo``: answer what is owed, wait until something is owed,
        repeat. It never ends on its own.
    """

    def owed() -> nu.Nu:
        """Whether the chat is waiting on a reply, read in a snapshot. Fresh at each site."""
        return ops.snapshot(chat.unanswered(plane_id, cell_id))

    return nu.ForeverDo(
        nu.IfDo(owed(), _turn(plane_id, cell_id, ui_plane_id=ui_plane_id, ask=ask))
        >> nu.IfDo(
            nu.Not(owed()),
            nu.ReactWhile(ops.snapshot(chat.changed(plane_id, cell_id)), nu.Not(owed()), nu.Noop()),
        )
    )


def performing(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    task: str,
    *,
    ask: Callable[..., nu.Nu],
) -> nu.Nu:
    """One job agent: the work cycle, one fixed task, and no drawing.

    The other entry point onto the same core. A job agent is a chat with the
    conversation taken out of it: nobody is talking, so there is nothing to
    hear and nothing to answer, and what is left is the cycle that does the
    thing. It narrates into its own Cell's state, so the panel a person opens
    over a job is the same panel a chat has.

    Args:
        plane_id: the Plane the job runs on.
        cell_id: the Cell on it doing the work. Its own state is where the
            trace goes.
        task: what to do, in prose. Fixed for the life of the term, which is
            the whole difference from a chat.
        ask: what one pass calls to reach the model.

    Returns:
        A Flow that runs the work cycle once and ends. It never draws and
        never appends a message; a job agent's result is what it changed.
    """
    panel = trace.Panel(plane_id, plane_id, cell_id, disp_cell_id=cell_id)
    session = trace.session_slots(panel)
    body = (
        panel.heard(nu.Str(task))
        >> memory.cleared(plane_id, cell_id)
        >> ops.atomic_state(_opened(session, nu.Dict.of(role="user", content=nu.Str(task))))
        >> cycles.work(session=session, panel=panel, ask=ask, state=_world(plane_id))
    )
    return nu.With(
        nu.Provide(dict, {}),
        body=nu.TryCatch(body, catch=panel.crashed(nu.Attr("error"))),
    )


def _turn(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    ask: Callable[..., nu.Nu],
) -> nu.Nu:
    """One input, worked and then answered, and what closes it.

    Working memory is the chat's own and lives in the store, under the Cell
    that talks: :mod:`nuspace.agent.session` says why it is nested there
    rather than named bare. A turn still starts on an empty one, but emptying
    it is a write now rather than a fresh dict.

    The one dict left is still provided per turn, and it is where ``Run.done``
    lives and where any ``nu.mem`` Shape the model invents lands, out of the way
    of the store. ``Run`` stays flat and untagged deliberately: the model ends
    the work cycle by redeclaring that Shape in its own module and setting the
    slot, so a ``Run`` addressed anywhere but where a bare redeclaration
    reaches is a ``Run`` that silently never ends anything.
    """

    def owed() -> nu.Nu:
        """Whether the chat is still waiting, read in a snapshot. Fresh at each site."""
        return ops.snapshot(chat.unanswered(plane_id, cell_id))

    panel = trace.Panel(ui_plane_id, plane_id, cell_id)
    session = trace.session_slots(panel)
    world = _world(ui_plane_id, plane_id=plane_id, cell_id=cell_id)
    body = (
        # The first row of the turn, and the only one that needs no model call
        # to write. Before the clear, because a person watching wants the
        # panel to move the instant the turn starts.
        panel.heard(trace.asked(plane_id, cell_id))
        >> memory.cleared(plane_id, cell_id)
        >> ops.atomic_state(_opened(session, _opening(plane_id, cell_id, ui_plane_id, panel)))
        >> cycles.work(session=session, panel=panel, ask=ask, state=world)
        >> ops.atomic_state(
            session.messages.append(
                nu.Dict.of(role="user", content=nu.Str(prompt.read(prompt.ANSWER)))
            )
        )
        >> cycles.answer(
            session=session, panel=panel, ask=ask, ui_plane_id=ui_plane_id, state=world
        )
        # The one place the host speaks. A turn that drew nothing left the
        # chat owed a reply, and nothing but this stops the loop going
        # straight back round the same question.
        >> nu.IfDo(
            owed(),
            chat.say(
                plane_id,
                cell_id,
                chat.ROLE_SYSTEM,
                _stopped(plane_id, cell_id),
            ),
        )
    )
    return nu.With(
        nu.Provide(dict, {}),
        body=nu.TryCatch(
            body,
            catch=chat.say(
                plane_id,
                cell_id,
                chat.ROLE_SYSTEM,
                nu.Str(CRASHED) + nu.ToStr(nu.Attr("error")),
            )
            >> panel.crashed(nu.Attr("error")),
        ),
    )


def _stopped(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """What to tell a person whose turn ended without an answer.

    Whichever cycle stopped wrote the account, so this reads it back rather
    than working anything out: it knows that a turn did not answer and nothing
    else, and "that run ended without an answer" is exactly the sentence
    somebody reads twice and still cannot act on.

    Floored to :data:`SILENT`, because a turn can end owing a reply without
    either cycle having given up: an answer that landed and then a person
    talking again inside the same turn would be one.
    """
    stalled = memory.stalled_of(plane_id, cell_id)
    said = nu.Str(nu.If(nu.Gt(nu.Len(stalled), nu.Int(0)), nu.Str(stalled), nu.Str(SILENT)))
    return said + nu.Str(ASK_AGAIN)


def _opened(session: nu.Nu, first: nu.Nu) -> nu.Nu:
    """Throw away last turn's conversation and start this one on ``first``.

    Emptied and then appended to, rather than set to a one element list, and
    that is not style. A kv list slot written with ``set`` routes each
    element's own type through the registry, and in a pool worker that
    registry is on the far end of a proxy and answers ``ViewRegistryError: No
    view registered for type dict``. ``append`` of the same dict into the same
    slot carries. The seed-then-append spelling is the one the Nu docs teach
    anyway, so this is what they say to write and it is also the one that
    works. **The proxied ``set`` is a bug and it is reported, not dodged**:
    nothing else here is shaped around it.

    No bracket: the caller commits it, ``first`` read inside the same commit.
    """
    return session.messages.set(nu.List.of()) >> session.messages.append(first)


def _world(
    ui_plane_id: nu.StrArg,
    *,
    plane_id: nu.StrArg | None = None,
    cell_id: nu.StrArg | None = None,
) -> nu.Nu:
    """What the model is shown after each of its programs ran.

    The Cells already on the Plane that draws are in it deliberately: a model
    that cannot see what it drew draws it again. So is the conversation, where
    there is one, because an answer composed out of what was actually said
    beats an answer composed out of what a model remembers saying.

    A bare read of both stores: the pass reads it inside the commit that
    writes the observation.
    """
    shown = {
        "planes": ops.planes(),
        "drawn": ops.cells(ui_plane_id),
    }
    if plane_id is not None and cell_id is not None:
        shown["said"] = chat.messages_of(plane_id, cell_id)
    return nu.Dict.of(**shown)


def _opening(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    ui_plane_id: nu.StrArg,
    panel: trace.Panel,
) -> nu.Nu:
    """A turn's first user message: where this chat is, and what was said.

    The four ids ride in the message rather than in the system prompt because
    the prompt is a python string built once and the ids are terms the running
    tree resolves. The labels are the words the prompt uses for them, so a
    model copying one off this message is copying the thing the prose told it
    to look for.

    The conversation is restated at the top of every turn even when the
    endpoint kept its session. Not every endpoint keeps one, a served model
    holds nothing between calls, and one that does can still lose it: a
    transcript deleted, a space moved to another machine. The record in the
    store is the one copy nothing loses, so every turn is told everything, and
    a turn whose endpoint remembered is told it twice for the price of a page
    of tokens.
    """
    return nu.Dict.of(
        role="user",
        content=nu.Str(prompt.read(prompt.OPENING))
        + nu.Str("\n\nchat plane: ")
        + nu.ToStr(plane_id)
        + nu.Str("\nchat cell: ")
        + nu.ToStr(cell_id)
        + nu.Str("\nui plane: ")
        + nu.ToStr(ui_plane_id)
        + nu.Str("\npanel cell: ")
        + nu.ToStr(panel.cell())
        + nu.Str("\n\nWhat has been said, oldest first:\n\n")
        + nu.ToStr(nu.Repr(chat.messages_of(plane_id, cell_id))),
    )
