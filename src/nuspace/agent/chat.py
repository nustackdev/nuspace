"""The conversation a chat holds: what was said, by whom, in order.

A chat is two Planes, the one a person looks at and a headless one nested
under it that talks, and neither has a container of its own. What was said
lives in the state of the Cell that runs the model, which is where a Cell's
state always lives. These are the terms that read and write it, and they are
the one spelling of the address: the Cell that talks and the Cell that draws
both come through here rather than each writing out a ref chain of its own.

**The conversation and the run are two things.** The Cell is the run: a
program, a plane run, a failure on its row. That is machinery and nobody
is talking in it. The conversation is what was *said*, and for a chat saying
something is an **action**: the model's only output is a Nu term, so it speaks
by emitting a program that appends here. That is the same primitive as
everything else it does, so a cron job, an app or a person at a REPL posts the
same way and a reader cannot tell them apart.

A message is a plain ``{role, text}`` dict rather than a Shape, so appending
is one call a model can write without looking anything up.

**The two Planes find each other through their own state.** Each holds the
other's id in :class:`Pair`, written once by the submit that made the pair,
so no program has an id baked into its source and the tree is left to say
only where the talking Plane hangs. Nested under the Plane that draws, it goes
when the chat goes.

:func:`submit` is the one op here that reaches past the conversation, and it
reaches three times. A chat is made with nothing behind it, and the first
message is what makes the Plane that talks and starts it. Every message puts
up the turn's display Cell first, because the panel has to be on the screen
the instant somebody presses send, and the agent that would otherwise draw it
is not awake yet. The two stores are two files, so these are a few commits in
a fixed order: the talking Plane, the panel, the message, the start.

**A turn answers by drawing.** The model's reply is not a line of text in a
timeline nuspace ships: it is one or more Cells appended to the Plane that
draws the chat, and one of them is how the person answers next. The reply
affordance is a program the model wrote, so it can be a box, three buttons, a
form, or a diff with approve and reject, and it is live rather than a render
of a payload because a Cell's program is Nu. :func:`draw` is that append. It
is here rather than in :mod:`nuspace.ops.cell` because what a turn draws is
part of the turn, and the address it goes to is a chat's.

**What is drawn changes every turn and the record does not.** Whatever the
person does through whatever the model drew comes back here as ``{role,
text}``, so everything that reads a chat reads one shape however the question
was put. Cells are presentation, ``messages`` is what happened.

``trace`` is the third thing kept here, and the one thing kept somewhere else.
It is what the agent is doing while it is doing it: the host's fixed states
between the links of a pass, and the model's own notes about what it changed.
One turn's trace lives in **that turn's display Cell's own state**, because a
Cell's state is where a Cell's state goes. It used to be one list beside the
conversation that every turn emptied, and a list that gets emptied is a panel
that can only ever show the turn you are standing in: scrolling back to turn
one showed turn four's work, or nothing. A list per display Cell is what makes
a chat readable a week later, and it costs no bookkeeping, because the Cell
that draws a turn is the Cell that turn writes into.

The last two things here are the two numbers a turn runs under, and they are
in the store for one reason: a chat that is grinding can be given more room
without being restarted, and it cannot be restarted, because a turn that was
cut off is a turn nobody can resume. :func:`budget_of` and
:func:`patience_of` read them, :func:`allow` writes them, and the loop asks
again on every pass.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace import ops
from nuspace.ops.utils import MintId, atomic_state, snapshot
from nuspace.shapes import CellState, PlaneState, Space
from nuspace.system.services import init


__all__ = [
    "BUDGET",
    "BY",
    "CHAT_DISPLAY_ID",
    "CHAT_DISPLAY_NAME",
    "CHAT_OTHER_ID",
    "CHAT_OTHER_NAME",
    "CHAT_TALK",
    "CYCLES",
    "CYCLE_ANSWER",
    "CYCLE_WORK",
    "DEFAULT_BUDGET",
    "DEFAULT_PATIENCE",
    "DISPLAY",
    "DISPLAY_SOURCE",
    "KINDS",
    "KIND_DONE",
    "KIND_FAILED",
    "KIND_HEARD",
    "KIND_NOTE",
    "KIND_RUNNING",
    "KIND_THINKING",
    "KIND_WRITING",
    "MESSAGES",
    "OTHER_SOURCE",
    "PATIENCE",
    "ROLES",
    "ROLE_AGENT",
    "ROLE_SYSTEM",
    "ROLE_USER",
    "TALKER_BACKEND",
    "TRACE",
    "Own",
    "Pair",
    "allow",
    "budget_of",
    "changed",
    "draw",
    "drawn_of",
    "latest_display",
    "messages_of",
    "note",
    "patience_of",
    "say",
    "state",
    "submit",
    "talker_of",
    "trace_changed",
    "trace_of",
    "unanswered",
]


#: The key the conversation is kept under, in the talking Cell's own state.
MESSAGES = "messages"

#: The key the id of this turn's display Cell is kept under, beside it. One
#: fact, written by the op that made the Cell, rather than a number two
#: callers work out separately and disagree about.
DISPLAY = "display"

#: The key a chat's pass ceiling is kept under, beside the conversation. How
#: much room a turn gets is a fact about the chat and not about the host, and
#: it is here rather than in python so that a run already grinding can be
#: given more of it from anywhere that can write.
BUDGET = "budget"

#: And the key its patience is kept under: how many passes in a row may fail
#: the same way before the cycle stops.
PATIENCE = "patience"

#: The ceiling where nobody has said otherwise. Far away on purpose. It is not
#: a judgement about how long work should take, which is the model's; it is
#: the backstop under a spin the repeat guard cannot see, and anything that
#: reaches it was not going to finish.
DEFAULT_BUDGET = 100

#: And the patience where nobody has said otherwise. One failure, one repair
#: that failed the same way, one more: three identical passes is a model that
#: has stopped reading what it is handed, and a fourth costs money to confirm.
DEFAULT_PATIENCE = 3

#: A person typed it.
ROLE_USER = "user"

#: The model wrote it, by appending, in a program it emitted.
ROLE_AGENT = "agent"

#: The host wrote it about the run itself: it crashed, or it finished without
#: saying anything. Never about the work, which is the model's to report.
ROLE_SYSTEM = "system"

#: Every role a reader knows. Anything else reads as ``system``, so a program
#: inventing a role is legible rather than invisible.
ROLES = (ROLE_USER, ROLE_AGENT, ROLE_SYSTEM)


#: The key the trace is kept under, in the display Cell's own state.
TRACE = "trace"

#: Doing what the person asked for, pass after pass, until the model is done.
CYCLE_WORK = "work"

#: Drawing what the person sees: the response and the next input form, in one
#: Cell, constructed and validated before it is appended.
CYCLE_ANSWER = "answer"

#: The two phases of a turn, in the order a turn takes them. A closed pair:
#: a turn works and then it answers, and there is no third thing to be doing.
CYCLES = (CYCLE_WORK, CYCLE_ANSWER)

#: The turn started, and this is what the person said.
KIND_HEARD = "heard"

#: A model call is out, and this is the prose that came back from the one
#: before it. It is working and has nothing to show for it yet.
KIND_THINKING = "thinking"

#: Source was pulled out of the reply. Which pass this is, against the budget.
KIND_WRITING = "writing"

#: The program constructed and ran, and this is what it came to.
KIND_RUNNING = "running"

#: It did not construct, or it raised. The diagnostic's first line.
KIND_FAILED = "failed"

#: A cycle finished, because the model said so in the program it wrote.
KIND_DONE = "done"

#: The model's own line about what it changed. The one kind the host does not
#: write: what a program was for is known only to whoever wrote it.
KIND_NOTE = "note"

#: Every kind a reader knows, and a closed set because a row is drawn *by* its
#: kind: one shape per kind is the whole of what makes the panel uniform, and
#: a kind nobody knows has no shape to draw. Anything else reads as
#: ``thinking``, which is the kind that claims the least.
KINDS = (
    KIND_HEARD,
    KIND_THINKING,
    KIND_WRITING,
    KIND_RUNNING,
    KIND_FAILED,
    KIND_DONE,
    KIND_NOTE,
)


# --- the Cells the host owns -------------------------------------------------

#: The Cell on the talking Plane that talks to the model and keeps what was
#: said in its own state. A name rather than a minted id, because the Plane it
#: is on holds it and nothing else.
CHAT_TALK = "c_talk"

#: The backend the talking Plane runs on: a process of its own, so a model
#: call that holds its worker holds nothing a person is looking at.
TALKER_BACKEND = "mp"

#: What the plane runs this module starts are recorded as ``by``.
BY = "chat"

#: What the id of a turn's display Cell starts with, before the turn number.
#: A stem rather than an id: there is one of these per turn and the number is
#: which turn it is, so ``c_disp_2`` is the second thing a person said and
#: everything the agent did about it.
CHAT_DISPLAY_ID = "c_disp_"

#: What one is called, before the same number. It reads as a divider down the
#: chat, which is the honest thing to call a panel that stands at the top of a
#: turn.
CHAT_DISPLAY_NAME = "turn "

# A call into `nuspace.agent` and nothing else, so behaviour written out here
# is behaviour every chat picks up from a newer nuspace: a seed has no
# migration. The panel is the one Cell in a chat the model never writes, never
# varies and cannot reach, so it is the one that most wants to be upgraded by
# installing a newer nuspace.
DISPLAY_SOURCE = '''import nuspace.agent
from nuspace import ops


def out():
    """What the agent did in this turn, as it does it.

    Its own two ids and nothing else. The trace this draws is in this Cell's
    own state, so there is no chat to name: the panel a turn writes into is
    the panel that turn put up.

    One list per turn rather than one list a turn empties, which is the whole
    of why scrolling back to the first thing you asked shows what was done
    about it rather than what is being done now.
    """
    return nuspace.agent.display(ops.Here.plane, ops.Here.cell)
'''

#: What the id of a turn's escape hatch starts with, before the turn number.
#: One per answer and numbered with it, so the Cell a person says something
#: else in sits beside the answer they are saying it about.
CHAT_OTHER_ID = "c_other_"

#: What one is called. The same word the closed control reads, because to a
#: person they are one thing.
CHAT_OTHER_NAME = "other "

# The one affordance on a chat the model neither draws nor can suppress, and
# it is host owned for the same reason the panel is. A turn that drew three
# buttons and forgot the fourth leaves the person with nothing to say at all,
# and a way out that is only there when somebody remembered it is not a way
# out. So the host appends one of these under every answer and the model is
# never asked.
OTHER_SOURCE = '''import nu
import nustd.ui
from nustd.ui.refs.layout import AccordionRef
from nuspace import ops
from nuspace.agent import chat


#: The one section the control opens, and what the closed row reads. One word,
#: because what it stands under is whatever the turn offered: three buttons
#: and then "other".
OTHER = "other"

#: The section's body. An Accordion's body is a tree child rather than a
#: prop, and child ``i`` is the body of section ``i`` in the order the
#: children were first written, so one section wants exactly one of these.
BODY = "body"


def out():
    """A box for saying something this turn did not offer, folded away.

    Collapsed, because the answer above it is the answer and this is the way
    round it. Open, it is the same box the chat started in.

    Four refs and four boot writes, and none of them is decoration: writing a
    ref is what ships its chain to the browser and what makes the node there,
    so an accordion nothing writes has no section to open and a box nothing
    writes would first come into being on the submit that reads it.

    The Plane this Cell is on is the Plane that draws the chat, and that is
    what the submit is handed: the panel for the turn goes up on the Plane the
    person pressing send is looking at.

    The box is emptied after the submit and not before, because the submit is
    what reads it.
    """
    other = AccordionRef(OTHER, section_cls=nustd.ui.Accordion)
    body = nustd.ui.SectionRef(BODY, section_cls=nustd.ui.Column, parent_ref=other)
    box = nustd.ui.TextAreaRef("message", parent_ref=body)
    send = nustd.ui.ButtonRef("send", parent_ref=body)
    return (
        other.set_sections([{"id": OTHER, "label": OTHER}])
        >> box.set("")
        >> send.set_label("send")
        >> nu.ReactForever(
            send.on_click(),
            chat.submit(ops.Here.plane, nu.Str(box)) >> box.set(""),
        )
    )
'''


# --- where it is kept --------------------------------------------------------


class Own(CellState):
    """A chat Cell's own state: one dict, keyed by the names above.

    The talking Cell keeps the conversation and its two numbers in it, a
    display Cell keeps its turn's trace. One container per Cell, and nothing
    else of the Cell's in it, which is what lets a watch on it be the whole
    of what wakes a reader.
    """

    state = nustd.kv.DictRef.slot(object)


class Pair(PlaneState):
    """Which Plane is on the other side of a chat, kept in each Plane's own state.

    ``talker`` is written on the Plane that draws, ``drawn`` on the Plane that
    talks. Both by the submit that made the pair, and never again: plane ids
    do not change.
    """

    talker = nustd.kv.StrRef.slot()
    drawn = nustd.kv.StrRef.slot()


def _own(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A Cell's own state, whichever Cell it is.

    A fresh ref at every call site. One node in two tree positions is one
    node, and a subscription is a handle the first holder to end would close
    under the other.
    """
    return ops.cell_state(plane_id, cell_id, Own.state)


def _held(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """The leaf the conversation is kept in. Fresh, for the reason above."""
    return _own(plane_id, cell_id)[MESSAGES]


def _said(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """The conversation as it lies, empty where nothing has been said.

    Floored, because an unwritten leaf reads EMPTY, which flows through every
    expression it touches and refuses to be stored.
    """
    held = _held(plane_id, cell_id)
    return nu.If(held.exists(), nu.List(held), nu.List.of())


def _turn(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Which turn a chat is on: how many times a person has said something.

    A turn is one input looped until done, so counting inputs counts turns,
    and nothing has to store a number that a restart could lose. It only ever
    goes up, and it goes up exactly once per :func:`submit`, which is what
    makes ``c_disp_<n>`` unique without minting anything.

    A reply the model appends does not move it, which is the point: the whole
    of a turn, however many passes it takes, writes into the one panel.
    """
    spoke = nu.Filter(
        nu.List(_said(plane_id, cell_id)),
        lambda said: nu.Eq(
            nu.ToStr(nu.Dict(said).get_item("role", ROLE_SYSTEM)), nu.Str(ROLE_USER)
        ),
    )
    return nu.Len(nu.List(nu.Collect(spoke)))


def _numbered(stem: str, turn: nu.Nu) -> nu.Nu:
    """``stem`` with the turn number after it: an id, or what it is called."""
    return nu.Str(stem) + nu.ToStr(turn)


def _addressed(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg) -> nu.Nu:
    """Whether these ids name a display Cell that is really there.

    The emptiness test is not redundant and it has to come first. A store key
    may not hold an empty segment, and :func:`latest_display` answers ``""``
    for a chat nobody has spoken in. ``And`` short-circuiting is what keeps
    the guard total.
    """
    return nu.And(
        nu.Ne(nu.ToStr(disp_cell_id), nu.Str("")),
        ops.cell_exists(disp_plane_id, disp_cell_id),
    )


def _kept(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg) -> nu.Nu:
    """The leaf a turn's trace is kept in. Fresh at every call site."""
    return _own(disp_plane_id, disp_cell_id)[TRACE]


def _traced(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg) -> nu.Nu:
    """The trace as it lies, empty where the turn has written none.

    Floored like :func:`_said`, and guarded on the id besides: a display Cell
    exists from the submit that made it, but the id read back for a chat
    nobody has spoken in is ``""``, and an empty key segment is no address.
    """
    kept = _kept(disp_plane_id, disp_cell_id)
    return nu.If(
        nu.And(nu.Ne(nu.ToStr(disp_cell_id), nu.Str("")), kept.exists()),
        nu.List(kept),
        nu.List.of(),
    )


# --- the pair ----------------------------------------------------------------


def talker_of(ui_plane_id: nu.StrArg) -> nu.Str:
    """The Plane that talks for the chat drawn on ``ui_plane_id``. ``""`` before anybody spoke."""
    return ops.plane_state(ui_plane_id, Pair.talker).fallback("")


def drawn_of(plane_id: nu.StrArg) -> nu.Str:
    """The Plane a talking Plane draws into. ``""`` for a Plane that is not one."""
    return ops.plane_state(plane_id, Pair.drawn).fallback("")


class _Submitting(nu.Shape):
    """What :func:`submit` works out on the way, under names fixed at build."""

    talker = nu.StrRef.slot()
    fresh = nu.BoolRef.slot()
    turn = nu.IntRef.slot()


def _paired(ui_plane_id: nu.StrArg, talk: nu.StrArg) -> nu.Nu:
    """The talking Plane, made under the Plane that draws, and the pair recorded. Three commits.

    Headless and nested: nothing draws it, and dropping the chat drops it. It
    records the registered Plane the chat was made from as its own
    ``made_by``, because that is what it is part of.
    """
    talker = _Submitting.talker
    drawn = Space.planes[ui_plane_id]
    return (
        talker.set(MintId("p"))
        >> ops.add_plane(
            talker,
            backend=TALKER_BACKEND,
            name=drawn.name.fallback(""),
            parent=ui_plane_id,
            ui=False,
            made_by=drawn.props.made_by.fallback(""),
        )
        >> ops.add_cell(talker, talk, cell_id=CHAT_TALK, name="talk")
        >> atomic_state(
            ops.plane_state(ui_plane_id, Pair.talker.set(talker))
            >> ops.plane_state(talker, Pair.drawn.set(ui_plane_id))
        )
    )


# --- write -------------------------------------------------------------------


def say(plane_id: nu.StrArg, cell_id: nu.StrArg, role: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """Append one message to a chat. The whole write surface there is.

    There is no edit and no delete-one on purpose: a conversation is a log,
    and a participant that could rewrite what it said earlier would make the
    transcript stop being evidence of what happened.

    Guarded on the Cell, because a write under a key nobody made vivifies the
    row and a chat that was deleted would grow state out of a late reply.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
        role: who is speaking. Not validated: an unknown role renders as
            ``system`` rather than disappearing, and a store that refused one
            would be a store that can lose a message. ``user`` is the one to
            leave alone: a person's word arrives through :func:`submit`, which
            also puts up the panel the answer is narrated into, and a ``user``
            message appended here would be a turn with nowhere to say what it
            is doing.
        text: what was said, verbatim.
    """
    return atomic_state(
        nu.IfDo(
            ops.cell_exists(plane_id, cell_id),
            _own(plane_id, cell_id).set_item(
                MESSAGES,
                nu.List(_said(plane_id, cell_id))
                + nu.List.of(nu.Dict.of(role=nu.Str(role), text=nu.Str(text))),
            ),
        )
    )


def submit(ui_plane_id: nu.StrArg, text: nu.StrArg, *, talk: nu.StrArg | None = None) -> nu.Nu:
    """A person said something: put this turn's panel up, record it, and start the chat.

    The first message is what makes a chat: before it there is nothing behind
    the Plane that draws, and this is what makes the Plane that talks, with
    ``talk`` as its one Cell, puts it on init's boot list so it comes back up
    with the space, and starts it. Every message after that only appends,
    because the Plane is already up and hears the write.

    The panel is the host's rather than the agent's for one reason: a run
    takes as long as it takes, and the panel that says what it is doing has to
    be on the screen before it has done anything. An agent that drew its own
    panel would draw it after waking, on the far side of the first model call,
    which is exactly the minute the person is watching a blank chat. So the
    host draws it, on the same press that asked the question.

    The commits go in a fixed order: the talking Plane, the panel, the message
    with the panel's id beside it, then the start. The panel goes up before the
    message lands, so a talking Cell woken by the message always finds the
    panel it is to narrate into. Its number is what the message about to be
    appended will make the turn count.

    Empty text is dropped rather than appended. A submit with nothing in it is
    a stray click, and a chat that started on one would ask a model an empty
    question.

    Args:
        ui_plane_id: the Plane that draws the chat, which is where the panel
            goes. Nothing is written when that Plane is not there.
        text: what the person wrote.
        talk: the talking Cell's program, for the first message to make the
            Plane that talks with. Which model a chat talks to is a fact about
            the chat, so it comes from whoever made the chat. Without it, a
            chat nobody has spoken in yet takes nothing.
    """
    talker, fresh, turn = _Submitting.talker, _Submitting.fresh, _Submitting.turn
    made = nu.IfDo(fresh, _paired(ui_plane_id, talk)) if talk is not None else nu.Noop()
    panel = ops.add_cell(
        ui_plane_id,
        DISPLAY_SOURCE,
        cell_id=_numbered(CHAT_DISPLAY_ID, turn),
        name=_numbered(CHAT_DISPLAY_NAME, turn),
    )
    said = atomic_state(
        nu.IfDo(
            ops.cell_exists(talker, CHAT_TALK),
            _own(talker, CHAT_TALK).set_item(
                MESSAGES,
                nu.List(_said(talker, CHAT_TALK))
                + nu.List.of(nu.Dict.of(role=nu.Str(ROLE_USER), text=nu.Str(text))),
            )
            >> _own(talker, CHAT_TALK).set_item(DISPLAY, _numbered(CHAT_DISPLAY_ID, turn)),
        )
    )
    started = nu.IfDo(
        nu.And(fresh, snapshot(ops.plane_exists(talker))),
        init.boot(talker) >> ops.plane_run(talker, by=BY),
    )
    # The emptiness test first, for the reason :func:`_addressed` gives: no
    # Plane that talks reads back ``""``, and that is no key.
    body = made >> nu.IfDo(
        nu.And(talker != "", snapshot(ops.cell_exists(talker, CHAT_TALK))),
        turn.set(nu.Int(snapshot(_turn(talker, CHAT_TALK))) + 1) >> panel >> said >> started,
    )
    asked = nu.And(nu.Gt(nu.Len(nu.Str(text)), nu.Int(0)), snapshot(ops.plane_exists(ui_plane_id)))
    return nu.IfDo(
        asked,
        nu.Frame(
            _Submitting,
            body,
            talker=snapshot(talker_of(ui_plane_id)),
            fresh=talker == "",
            turn=0,
        ),
    )


def draw(ui_plane_id: nu.StrArg, source: nu.StrArg, *, name: nu.StrArg | None = None) -> nu.Nu:
    """Append one turn to the Plane that draws a chat, as the Cell it is.

    How a model answers. It emits the source of a Cell and this is what lands
    it on the end of the Plane the person is looking at, so an answer is a
    program bound to the store rather than a payload something else renders,
    and the person can open it in the editor afterwards because what landed is
    an ordinary Cell.

    A turn draws and never acts, and that is the whole discipline of one. A
    Cell's program persists and runs again every time somebody opens the
    chat, so a turn that *did* something would do it again, a week later,
    with nobody asking. The agent acts from the Plane it runs on. The one
    exception is an input a person clicks, which acts because somebody asked
    it to right then.

    Appended and never placed: a turn goes after the turn before it, and
    whatever the Plane was seeded with keeps the place it was born in.

    The id is minted when it runs and the caller never learns it, because
    nothing addresses a turn once it is drawn.

    Args:
        ui_plane_id: the Plane that draws the chat. The whole thing is a no-op
            when that Plane is not there.
        source: the program, a python module with an ``out`` entry point.
        name: what to call it. Unnamed when absent.
    """
    return ops.add_cell(ui_plane_id, source, name="" if name is None else name)


def state(
    disp_plane_id: nu.StrArg,
    disp_cell_id: nu.StrArg,
    cycle: nu.StrArg,
    kind: nu.StrArg,
    text: nu.StrArg,
) -> nu.Nu:
    """Record one thing the agent did on the way to an answer.

    Not a message, and the difference is who it is for. A message was said to
    somebody and is kept forever, which is why nothing edits or drops one. A
    trace row is the agent narrating itself while the turn runs: the host
    writes it between the links of a pass, and somebody reading the
    conversation back later wants none of it.

    Appends rather than replaces, so a slow turn reads as a list that grows
    instead of one line that flickers. Nothing ever clears it: the list
    belongs to one turn's panel and that turn is over when it stops growing.

    Guarded on the display Cell for the reason :func:`say` is guarded on the
    talking one: a write under a key nobody made vivifies the row, and a chat
    deleted mid turn would grow state out of a row arriving late.

    Args:
        disp_plane_id: the Plane that draws the chat.
        disp_cell_id: the display Cell this turn writes into, which is what
            :func:`latest_display` answers.
        cycle: which half of the turn this happened in, one of
            :data:`CYCLES`. Not validated, for the reason a kind is not.
        kind: one of :data:`KINDS`, which is what a reader draws it by. Not
            validated, for the reason a role is not: an unknown kind reads as
            ``thinking`` rather than disappearing, and a store that refused
            one would be a store that can lose what happened.
        text: what to show for it, in one line.
    """
    return atomic_state(
        nu.IfDo(
            _addressed(disp_plane_id, disp_cell_id),
            _own(disp_plane_id, disp_cell_id).set_item(
                TRACE,
                nu.List(_traced(disp_plane_id, disp_cell_id))
                + nu.List.of(nu.Dict.of(cycle=nu.Str(cycle), kind=nu.Str(kind), text=nu.Str(text))),
            ),
        )
    )


def note(
    disp_plane_id: nu.StrArg,
    disp_cell_id: nu.StrArg,
    cycle: nu.StrArg,
    text: nu.StrArg,
) -> nu.Nu:
    """Say what was changed, in the model's own words. Its one row to write.

    :func:`state` with the kind already filled in, and it exists as a separate
    name because of who calls it. The host writes states from the loop, where
    an extra argument costs nothing. This one the model writes from inside a
    program it is composing, so it is the one call in this module whose
    spelling has to fit in a sentence of a prompt.

    The host cannot write this row for it. What a program was *for* is known
    only to whoever wrote it, and "renamed the notes plane" is a sentence no
    host composes out of a term it did not author.

    Args:
        disp_plane_id: the Plane that draws the chat.
        disp_cell_id: the display Cell this turn writes into.
        cycle: which half of the turn this happened in, one of :data:`CYCLES`.
        text: what changed, in one line.
    """
    return state(disp_plane_id, disp_cell_id, cycle, KIND_NOTE, text)


def allow(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    budget: nu.IntArg | None = None,
    patience: nu.IntArg | None = None,
) -> nu.Nu:
    """Give this chat more room, or less. Both numbers, or either one.

    The point of keeping them in the store rather than in python is that this
    can be run against a chat that is already grinding: the loop reads both on
    every pass, so a ceiling raised now is a ceiling the turn in flight gets.
    Nothing has to be restarted, and a restart is not even available, since a
    turn that was cut off is a turn nobody can resume.

    Guarded on the Cell like every other write here, and one commit, so a
    caller setting both never has a pass read the new ceiling against the old
    patience.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that talks.
        budget: how many passes a work cycle may take. Left alone when absent.
        patience: how many passes in a row may fail the same way before the
            cycle gives up. Left alone when absent.
    """
    written = nu.Noop()
    if budget is not None:
        written = written >> _own(plane_id, cell_id).set_item(BUDGET, nu.Int(budget))
    if patience is not None:
        written = written >> _own(plane_id, cell_id).set_item(PATIENCE, nu.Int(patience))
    return atomic_state(nu.IfDo(ops.cell_exists(plane_id, cell_id), written))


# --- read --------------------------------------------------------------------


def messages_of(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """The conversation, one ``{role, text}`` dict per message, oldest first.

    Rebuilt key by key rather than handed over as it lies. A list written into
    a kv leaf reads back as a *view*, and a view is a live cursor into the
    store rather than a value: msgpack cannot serialise one, so shipping the
    bare list is a frame that fails on the way out and an arm that reports
    itself once per write.
    """
    return nu.Collect(
        nu.Map(
            nu.List(_said(plane_id, cell_id)),
            lambda said: nu.Dict.of(
                role=nu.ToStr(nu.Dict(said).get_item("role", ROLE_SYSTEM)),
                text=nu.ToStr(nu.Dict(said).get_item("text", "")),
            ),
        )
    )


def trace_of(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg) -> nu.Nu:
    """One turn's trace, ``{cycle, kind, text}`` each, oldest first.

    Rebuilt key by key rather than handed over as it lies, for the reason
    :func:`messages_of` is: a list written into a kv leaf reads back as a
    *view*, and a view is a live cursor into the store rather than a value, so
    the bare list is a frame msgpack cannot pack and an arm that reports
    itself once per write. The Cell drawing this redraws on every row, which
    is the one place that failure would show up loudest.

    A row with nothing under ``kind`` floors to ``thinking`` and one with
    nothing under ``cycle`` floors to ``work``, rather than dropping out of the
    list: it is still something that happened, and those are the two that claim
    the least about it. A word nobody knows comes through as it was written,
    for the same reason an invented role does, and it is the reader that
    decides what an unknown one looks like.
    """
    return nu.Collect(
        nu.Map(
            nu.List(_traced(disp_plane_id, disp_cell_id)),
            lambda row: nu.Dict.of(
                cycle=nu.ToStr(nu.Dict(row).get_item("cycle", CYCLE_WORK)),
                kind=nu.ToStr(nu.Dict(row).get_item("kind", KIND_THINKING)),
                text=nu.ToStr(nu.Dict(row).get_item("text", "")),
            ),
        )
    )


def latest_display(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """The display Cell the running turn should be writing into.

    The id only, because the Plane it is on is the one the chat draws to, and
    whoever is asking this is holding that id already: the agent was handed it
    and the panel is running on it.

    Read back rather than worked out again. :func:`submit` is what made the
    Cell, so :func:`submit` is what says which one it is, and a second caller
    counting messages for itself would be a second answer to one question.

    ``""`` for a chat nobody has spoken in, which is a chat with no panel yet.
    Every write here is guarded against that, so a row addressed at it goes
    nowhere instead of raising.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
    """
    return nu.ToStr(_own(plane_id, cell_id).get_item(DISPLAY, ""))


def budget_of(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """How many passes a work cycle on this chat may take.

    :data:`DEFAULT_BUDGET` where nobody has said otherwise, which is almost
    always: the number is here to be raised on the one chat that needs it, not
    to be set on every chat that does not.

    Read fresh on every pass rather than settled when the turn started, which
    is the whole of why it is a key and not an argument.
    """
    return nu.Int(_own(plane_id, cell_id).get_item(BUDGET, DEFAULT_BUDGET))


def patience_of(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """How many passes in a row may fail the same way before a cycle gives up.

    :data:`DEFAULT_PATIENCE` where nobody has said otherwise. Raising it is
    for a model working against something that genuinely reports one error for
    several different mistakes; lowering it is for an expensive endpoint.
    """
    return nu.Int(_own(plane_id, cell_id).get_item(PATIENCE, DEFAULT_PATIENCE))


def unanswered(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """Whether the last word was the person's, so the chat owes a reply.

    The whole of when a chat works. A Cell that came up because somebody
    pressed send finds the message already written, so it cannot have heard
    the change and has to ask this instead; a Cell that came back after a
    reboot asks the same question and answers nothing, because the last thing
    said was the model's. So a restart never replays a conversation and an
    outstanding question is never dropped.

    False on an empty conversation, which is a chat nobody has started.
    """
    said = nu.List(_said(plane_id, cell_id))
    last = nu.Dict(nu.List(_said(plane_id, cell_id))[nu.Len(said) - nu.Int(1)])
    return nu.And(
        nu.Gt(nu.Len(said), nu.Int(0)),
        nu.Eq(nu.ToStr(last.get_item("role", ROLE_SYSTEM)), nu.Str(ROLE_USER)),
    )


def changed(plane_id: nu.StrArg, cell_id: nu.StrArg) -> nu.Nu:
    """A fresh subscription that fires on every message.

    A read rather than a write, and the address is here for the same reason
    the writes are: two callers spelling one ref chain is two chances to spell
    it differently. Fresh at every call site, because two arms holding one
    subscription hold one handle and the first to end closes it under the
    other.

    **The Cell's ``state``, not the leaf the conversation is in.** A leaf
    watch fires in the process that opened the store and never in a worker on
    the far end of the proxied change feed: it binds, it reports nothing, and
    a chat answers the message it came up holding and then goes deaf. A watch
    on the container above it carries.

    So this hears the display id too, which is written by the same press that
    writes the message and says nothing new. It does not hear the turn's
    working memory, which is kept beside ``state`` rather than in it, so the
    loop is not woken once a pass by a write it does not read. Nor the trace,
    which a turn narrates into the panel's state, on the Plane that draws.
    """
    return _own(plane_id, cell_id).on_change()


def trace_changed(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg) -> nu.Nu:
    """A fresh subscription that fires on every row of one turn's trace.

    The display Cell's own ``state``, which is the container the trace is a
    key in. A child scoped watch never carries to a worker, so the finest
    thing that can wake one is a container, and nothing else is kept in this
    one: a panel drawing a turn is woken by that turn and by nothing else.

    Fresh at each call site, because a subscription is a handle: two arms
    sharing one node share one handle, and the first of them to end closes it
    under the other.

    Called with the panel's own two ids, so there is no empty id to guard
    against here the way the writes guard against one.
    """
    return _own(disp_plane_id, disp_cell_id).on_change()
