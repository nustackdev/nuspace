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
owed a reply, and that is the one place the host speaks.

The endpoint is not here. It is brought up once, around this whole loop, so a
Claude Code session lasts as long as the chat rather than as long as a turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace import ops
from nuspace.agent import cycles, prompt, trace
from nuspace.agent import session as memory
from nuspace.shapes import Space


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["CRASHED", "SILENT", "answering", "performing"]


#: What the host says when a turn ended without the model answering. The host
#: speaks here and nowhere else, and it earns its place twice: silence reads
#: as a broken space rather than as an unfinished job, and an answered
#: question is what stops this asking the same one again.
SILENT = "That turn ended without an answer. Ask again, or ask for less."

#: Same, for the loop itself dying. The model's own mistakes never reach this:
#: a module that will not construct is fed back to it and the turn carries on.
CRASHED = "The turn crashed and stopped: "


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
        ui_plane_id: the Plane the agent draws its answers onto.
        ask: what one pass calls to reach the model. Called with ``messages=``
            and yields a dict with ``text`` in it. Handed in rather than chosen
            here, because which model a chat talks to is the endpoint's
            business and the loop is the same either way.
        root: the Space shape class.

    Returns:
        A ``ForeverDo``: answer what is owed, wait until something is owed,
        repeat. It never ends on its own.
    """

    def owed() -> nu.Nu:
        """Whether the chat is waiting on a reply. Fresh at each call site."""
        return ops.chat.unanswered(plane_id, cell_id, root=root)

    return nu.ForeverDo(
        nu.IfDo(owed(), _turn(plane_id, cell_id, ui_plane_id=ui_plane_id, ask=ask, root=root))
        >> nu.IfDo(
            nu.Not(owed()),
            nu.ReactWhile(
                ops.chat.changed(plane_id, cell_id, root=root), nu.Not(owed()), nu.Noop()
            ),
        )
    )


def performing(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    task: str,
    *,
    ask: Callable[..., nu.Nu],
    root: type[Space] = Space,
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
        root: the Space shape class.

    Returns:
        A Flow that runs the work cycle once and ends. It never draws and
        never appends a message; a job agent's result is what it changed.
    """
    panel = trace.Panel(plane_id, plane_id, cell_id, root, disp_cell_id=cell_id)
    session = trace.session_slots(panel)
    body = (
        panel.heard(nu.Str(task))
        >> memory.cleared(plane_id, cell_id, root=root)
        >> _opened(session, nu.Dict.of(role="user", content=nu.Str(task)))
        >> cycles.work(session=session, panel=panel, ask=ask, state=_world(plane_id, root=root))
    )
    return nu.With(
        nu.Provide(dict, {}),
        body=nu.TryCatch(body, catch=panel.crashed(nu.AttrRef("error"))),
    )


def _turn(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    ask: Callable[..., nu.Nu],
    root: type[Space],
) -> nu.Nu:
    """One input, worked and then answered, and what closes it.

    Working memory is the chat's own and lives in the store, under the Cell
    that talks: :mod:`nuspace.agent.session` says why it is nested there
    rather than named bare. A turn still starts on an empty one, but emptying
    it is a write now rather than a fresh dict.

    The one dict left is still provided per turn, and it is where ``Run.done``
    lives and where any ``nustd.mem`` the model invents lands, out of the way
    of the store. ``Run`` stays flat and untagged deliberately: the model ends
    the work cycle by redeclaring that Shape in its own module and setting the
    slot, so a ``Run`` addressed anywhere but where a bare redeclaration
    reaches is a ``Run`` that silently never ends anything.
    """

    def owed() -> nu.Nu:
        """Whether the chat is still waiting. Fresh at each call site."""
        return ops.chat.unanswered(plane_id, cell_id, root=root)

    panel = trace.Panel(ui_plane_id, plane_id, cell_id, root)
    session = trace.session_slots(panel)
    world = _world(ui_plane_id, root=root, plane_id=plane_id, cell_id=cell_id)
    body = (
        # The first row of the turn, and the only one that needs no model call
        # to write. Before the clear, because a person watching wants the
        # panel to move the instant the turn starts.
        panel.heard(trace.asked(plane_id, cell_id, root=root))
        >> memory.cleared(plane_id, cell_id, root=root)
        >> _opened(session, _opening(plane_id, cell_id, ui_plane_id, panel, root=root))
        >> cycles.work(session=session, panel=panel, ask=ask, state=world)
        >> session.messages.append(
            nu.Dict.of(role="user", content=nu.Str(prompt.read(prompt.ANSWER, root=root)))
        )
        >> cycles.answer(
            session=session, panel=panel, ask=ask, ui_plane_id=ui_plane_id, state=world
        )
        # The one place the host speaks. A turn that drew nothing left the
        # chat owed a reply, and nothing but this stops the loop going
        # straight back round the same question.
        >> nu.IfDo(
            owed(),
            ops.chat.say(plane_id, cell_id, ops.chat.ROLE_SYSTEM, SILENT, root=root),
        )
    )
    return nu.With(
        nu.Provide(dict, {}),
        body=nu.TryCatch(
            body,
            catch=ops.chat.say(
                plane_id,
                cell_id,
                ops.chat.ROLE_SYSTEM,
                nu.Str(CRASHED) + nu.ToStr(nu.AttrRef("error")),
                root=root,
            )
            >> panel.crashed(nu.AttrRef("error")),
        ),
    )


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
    """
    return session.messages.set(nu.List.of()) >> session.messages.append(first)


def _world(
    ui_plane_id: nu.StrArg,
    *,
    root: type[Space],
    plane_id: nu.StrArg | None = None,
    cell_id: nu.StrArg | None = None,
) -> nu.Nu:
    """What the model is shown after each of its programs ran.

    The Cells already on the Plane that draws are in it deliberately: a model
    that cannot see what it drew draws it again. So is the conversation, where
    there is one, because an answer composed out of what was actually said
    beats an answer composed out of what a model remembers saying.
    """
    shown = {
        "planes": ops.plane_ids(root=root),
        "drawn": ops.cell_ids(ui_plane_id, root=root),
    }
    if plane_id is not None and cell_id is not None:
        shown["said"] = ops.chat.messages_of(plane_id, cell_id, root=root)
    return nu.Dict.of(**shown)


def _opening(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    ui_plane_id: nu.StrArg,
    panel: trace.Panel,
    *,
    root: type[Space],
) -> nu.Nu:
    """A turn's first user message: where this chat is, and what was said.

    The four ids ride in the message rather than in the system prompt because
    the prompt is a python string built once and the ids are terms the running
    tree resolves. The labels are the words the prompt uses for them, so a
    model copying one off this message is copying the thing the prose told it
    to look for.

    The conversation is restated at the top of every turn even when the
    endpoint kept its session. A session is lost to any restart and the
    conversation is not, so the turn that comes back after one has to be told
    everything, and a turn that did not is told it twice for the price of a
    page of tokens.
    """
    return nu.Dict.of(
        role="user",
        content=nu.Str(prompt.read(prompt.OPENING, root=root))
        + nu.Str("\n\nchat plane: ")
        + nu.ToStr(plane_id)
        + nu.Str("\nchat cell: ")
        + nu.ToStr(cell_id)
        + nu.Str("\nui plane: ")
        + nu.ToStr(ui_plane_id)
        + nu.Str("\npanel cell: ")
        + nu.ToStr(panel.cell())
        + nu.Str("\n\nWhat has been said, oldest first:\n\n")
        + nu.ToStr(nu.Repr(ops.chat.messages_of(plane_id, cell_id, root=root))),
    )
