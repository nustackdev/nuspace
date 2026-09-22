"""The conversation a chat holds: what was said, by whom, in order.

A chat is a job with a label, so there is no shape here and no container of
its own. What was said lives in the state of the Cell that runs the model,
which is where a Cell's state always lives. These are the terms that read and
write it, and they are the one spelling of the address: the Cell that talks
and the Cell that draws both come through here rather than each writing out a
ref chain of its own.

**The conversation and the run are two things.** The Cell is the run: a
program, a restart policy, a failure on its row. That is machinery and nobody
is talking in it. The conversation is what was *said*, and for a chat saying
something is an **action**: the model's only output is a Nu term, so it speaks
by emitting a program that appends here. That is the same primitive as
everything else it does, so a cron job, an app or a person at a REPL posts the
same way and a reader cannot tell them apart.

A message is a plain ``{role, text}`` dict rather than a Shape, so appending
is one call a model can write without looking anything up.

:func:`submit` is the one op here that reaches past the conversation, and it
reaches twice. A chat is made at ``trigger: manual`` and the first message is
what starts it, so the append and the flip land in one commit or a chat is
observable holding a question with nothing running to answer it. That same
commit appends the turn's display Cell, because the panel has to be on the
screen the instant somebody presses send, and the agent that would otherwise
draw it is not awake yet.

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
"""

from __future__ import annotations

import nu
from nuspace.ops.cell import add_cell, cell_writes
from nuspace.ops.groups import CHAT_DISPLAY, CHAT_DISPLAY_ID, CHAT_DISPLAY_NAME
from nuspace.ops.utils import atomic
from nuspace.shapes import RESTART_NO, TRIGGER_BOOT, Space


__all__ = [
    "CYCLES",
    "CYCLE_ANSWER",
    "CYCLE_WORK",
    "DISPLAY",
    "KINDS",
    "KIND_DONE",
    "KIND_FAILED",
    "KIND_HEARD",
    "KIND_NOTE",
    "KIND_RUNNING",
    "KIND_THINKING",
    "KIND_WRITING",
    "MESSAGES",
    "ROLES",
    "ROLE_AGENT",
    "ROLE_SYSTEM",
    "ROLE_USER",
    "TRACE",
    "changed",
    "draw",
    "latest_display",
    "messages_of",
    "note",
    "say",
    "state",
    "submit",
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


#: What the row reader binds the message it is on under. Parallel arms share
#: one ``ctx.attrs``, so it is namespaced to this module.
_ITEM = "_nx_said"
_item = nu.DictAttrRef(_ITEM)

#: The same for a trace row, and a second name rather than the one above. One
#: Cell can draw the conversation and the trace in two parallel arms, and two
#: Maps binding one attr would each be reading the other's element.
_ROW = "_nx_row"
_row = nu.DictAttrRef(_ROW)

#: And a third, for counting what a person has said. The count is built inside
#: :func:`submit`, which is also appending a message, so it cannot borrow the
#: name the message reader uses.
_SPOKE = "_nx_spoke"
_spoke = nu.DictAttrRef(_SPOKE)


def _own(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """A Cell's own state, whichever Cell it is.

    A fresh ref at every call site. One node in two tree positions is one
    node, and a subscription is a handle the first holder to end would close
    under the other.
    """
    return root.planes[plane_id].cells[cell_id].state


def _held(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The leaf the conversation is kept in. Fresh, for the reason above."""
    return _own(plane_id, cell_id, root)[MESSAGES]


def _said(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The conversation as it lies, empty where nothing has been said.

    Floored, because an unwritten leaf reads EMPTY and every Query touching
    EMPTY collapses to INVALID, which writes nothing and raises nothing.
    """
    held = _held(plane_id, cell_id, root)
    return nu.If(held.exists(), nu.List(held), nu.List.of())


def _turn(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """Which turn a chat is on: how many times a person has said something.

    A turn is one input looped until done, so counting inputs counts turns,
    and nothing has to store a number that a restart could lose. It only ever
    goes up, and it goes up exactly once per :func:`submit`, which is what
    makes ``c_disp_<n>`` unique without minting anything: two people pressing
    send at the same moment are two messages, so they are two numbers.

    A reply the model appends does not move it, which is the point: the whole
    of a turn, however many passes it takes, writes into the one panel.
    """
    return nu.Len(
        nu.List(
            nu.Collect(
                nu.Filter(
                    nu.List(_said(plane_id, cell_id, root)),
                    nu.Eq(
                        nu.ToStr(_spoke.get_item(nu.Str("role"), nu.Str(ROLE_SYSTEM))),
                        nu.Str(ROLE_USER),
                    ),
                    key=_SPOKE,
                )
            )
        )
    )


def _numbered(stem: str, turn: nu.Nu) -> nu.Nu:
    """``stem`` with the turn number after it: an id, or what it is called."""
    return nu.Str(stem) + nu.ToStr(turn)


def _addressed(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """Whether these ids name a display Cell that is really there.

    The emptiness test is not redundant and it has to come first. A store key
    may not hold an empty segment, so ``contains("")`` raises out of the codec
    rather than reading as absent, and :func:`latest_display` answers ``""``
    for a chat nobody has spoken in. ``And`` short-circuiting is what keeps
    the guard total.
    """
    cells = root.planes[disp_plane_id].cells
    return nu.And(nu.Ne(nu.ToStr(disp_cell_id), nu.Str("")), cells.contains(disp_cell_id))


def _kept(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The leaf a turn's trace is kept in. Fresh at every call site."""
    return _own(disp_plane_id, disp_cell_id, root)[TRACE]


def _traced(disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The trace as it lies, empty where the turn has written none.

    Floored like :func:`_said`, and guarded on the id besides: a display Cell
    exists from the submit that made it, but the id read back for a chat
    nobody has spoken in is ``""``, and an empty key segment raises in the
    codec rather than reading as absent.
    """
    kept = _kept(disp_plane_id, disp_cell_id, root)
    return nu.If(
        nu.And(nu.Ne(nu.ToStr(disp_cell_id), nu.Str("")), kept.exists()),
        nu.List(kept),
        nu.List.of(),
    )


# --- write -------------------------------------------------------------------


def say(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    role: nu.StrArg,
    text: nu.StrArg,
    *,
    root: type[Space] = Space,
) -> nu.Nu:
    """Append one message to a chat. The whole write surface there is.

    There is no edit and no delete-one on purpose: a conversation is a log,
    and a participant that could rewrite what it said earlier would make the
    transcript stop being evidence of what happened.

    Guarded on the Cell, because a write under a key nobody made vivifies the
    row and a chat that was deleted would grow a Cell out of a late reply.

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
        root: the Space shape class.
    """
    cells = root.planes[plane_id].cells
    return atomic(
        nu.IfDo(
            cells.contains(cell_id),
            _own(plane_id, cell_id, root).set_item(
                MESSAGES,
                nu.List(_said(plane_id, cell_id, root))
                + nu.List.of(nu.Dict.of(role=nu.Str(role), text=nu.Str(text))),
            ),
        ),
        root,
    )


def submit(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    text: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    root: type[Space] = Space,
) -> nu.Nu:
    """A person said something: start the chat, and put this turn's panel up.

    Three facts in one commit, which is why this is an op rather than three.

    A chat is made at ``trigger: manual``, so nothing is running behind it
    until somebody talks; the first message flips the Plane to ``boot`` and the
    runtime brings it up. Every message after that only appends, because the
    Plane is already up and hears the write.

    The third is the display Cell, and it is the host's rather than the
    agent's for one reason: a run takes as long as it takes, and the panel
    that says what it is doing has to be on the screen before it has done
    anything. An agent that drew its own panel would draw it after waking, on
    the far side of the first model call, which is exactly the minute the
    person is watching a blank chat. So the host draws it, on the same press
    that asked the question.

    The emptiness test comes first in the sequence and that is load bearing: a
    Transaction sees its own writes, so asking after the append would always
    answer no and a chat would never start. The turn number is the other side
    of that coin and is read *after* the append on purpose, so the panel this
    press makes is numbered for the message this press wrote.

    Empty text is dropped rather than appended. A submit with nothing in it is
    a stray click, and a chat that started on one would ask a model an empty
    question.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
        text: what the person wrote.
        ui_plane_id: the Plane that draws the chat, which is where the panel
            goes. The append alone is a no-op when that Plane is not there.
        root: the Space shape class.
    """
    plane = root.planes[plane_id]

    def turn() -> nu.Nu:
        """Which turn this is, read after the append. Fresh at each site."""
        return _turn(plane_id, cell_id, root)

    return atomic(
        nu.IfDo(
            nu.And(
                plane.cells.contains(cell_id),
                nu.Gt(nu.Len(nu.Str(text)), nu.Int(0)),
            ),
            nu.IfDo(
                nu.Eq(nu.Len(_said(plane_id, cell_id, root)), nu.Int(0)),
                plane.props.trigger.set(nu.Str(TRIGGER_BOOT)),
            )
            >> _own(plane_id, cell_id, root).set_item(
                MESSAGES,
                nu.List(_said(plane_id, cell_id, root))
                + nu.List.of(nu.Dict.of(role=nu.Str(ROLE_USER), text=nu.Str(text))),
            )
            >> _own(plane_id, cell_id, root).set_item(DISPLAY, _numbered(CHAT_DISPLAY_ID, turn()))
            # The panel is about the Cell it is on and about nothing else, so
            # there is no subject to bake into it: it reads the trace out of
            # its own state, under its own two ids.
            >> cell_writes(
                ui_plane_id,
                CHAT_DISPLAY.render("", root=root),
                cell_id=_numbered(CHAT_DISPLAY_ID, turn()),
                name=_numbered(CHAT_DISPLAY_NAME, turn()),
                root=root,
            ),
        ),
        root,
    )


def draw(
    ui_plane_id: nu.StrArg,
    source: nu.StrArg,
    *,
    name: nu.StrArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Append one turn to the Plane that draws a chat, as the Cell it is.

    How a model answers. It emits the source of a Cell and this is what lands
    it on the end of the Plane the person is looking at, so an answer is a
    program bound to the store rather than a payload something else renders,
    and the person can open it in the editor afterwards because what landed is
    an ordinary Cell.

    ``restart`` is ``no``, and that is the whole discipline of a turn. A
    Cell's program persists and runs again on every reload, so a turn that
    *did* something would do it again, a week later, with nobody asking. A
    turn draws, and the agent acts from the Plane it runs on. The one
    exception is an input a person clicks, which acts because somebody asked
    it to right then.

    Appended and never placed: a turn goes after the turn before it, and
    whatever the Plane was seeded with keeps the place it was born in.

    The id is minted here and the caller never learns it, because nothing
    addresses a turn once it is drawn. Minted while the tree is built, so one
    of these is one turn: the same term run twice rewrites one Cell rather
    than appending a second.

    Args:
        ui_plane_id: the Plane that draws the chat. The whole thing is a no-op
            when that Plane is not there.
        source: the program, a python module with an ``out`` entry point.
        name: what to call it. The id when absent.
        root: the Space shape class.
    """
    return add_cell(ui_plane_id, source, name=name, restart=RESTART_NO, root=root)


def state(
    disp_plane_id: nu.StrArg,
    disp_cell_id: nu.StrArg,
    cycle: nu.StrArg,
    kind: nu.StrArg,
    text: nu.StrArg,
    *,
    root: type[Space] = Space,
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
    deleted mid turn would grow a Cell out of a state arriving late.

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
        root: the Space shape class.
    """
    return atomic(
        nu.IfDo(
            _addressed(disp_plane_id, disp_cell_id, root),
            _own(disp_plane_id, disp_cell_id, root).set_item(
                TRACE,
                nu.List(_traced(disp_plane_id, disp_cell_id, root))
                + nu.List.of(nu.Dict.of(cycle=nu.Str(cycle), kind=nu.Str(kind), text=nu.Str(text))),
            ),
        ),
        root,
    )


def note(
    disp_plane_id: nu.StrArg,
    disp_cell_id: nu.StrArg,
    cycle: nu.StrArg,
    text: nu.StrArg,
    *,
    root: type[Space] = Space,
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
        root: the Space shape class.
    """
    return state(disp_plane_id, disp_cell_id, cycle, KIND_NOTE, text, root=root)


# --- read --------------------------------------------------------------------


def messages_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """The conversation, one ``{role, text}`` dict per message, oldest first.

    Rebuilt key by key rather than handed over as it lies. A list written into
    a kv leaf reads back as a *view*, and a view is a live cursor into the
    store rather than a value: msgpack cannot serialise one, so shipping the
    bare list is a frame that fails on the way out and an arm that reports
    itself once per write.
    """
    return nu.Collect(
        nu.Map(
            nu.List(_said(plane_id, cell_id, root)),
            nu.Dict.of(
                role=nu.ToStr(_item.get_item(nu.Str("role"), nu.Str(ROLE_SYSTEM))),
                text=nu.ToStr(_item.get_item(nu.Str("text"), nu.Str(""))),
            ),
            key=_ITEM,
        )
    )


def trace_of(
    disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg, *, root: type[Space] = Space
) -> nu.Nu:
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
            nu.List(_traced(disp_plane_id, disp_cell_id, root)),
            nu.Dict.of(
                cycle=nu.ToStr(_row.get_item(nu.Str("cycle"), nu.Str(CYCLE_WORK))),
                kind=nu.ToStr(_row.get_item(nu.Str("kind"), nu.Str(KIND_THINKING))),
                text=nu.ToStr(_row.get_item(nu.Str("text"), nu.Str(""))),
            ),
            key=_ROW,
        )
    )


def latest_display(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
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
        root: the Space shape class.
    """
    return nu.ToStr(_own(plane_id, cell_id, root).get_item(DISPLAY, nu.Str("")))


def unanswered(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether the last word was the person's, so the chat owes a reply.

    The whole of when a chat works. A Cell that came up because somebody
    pressed send finds the message already written, so it cannot have heard
    the change and has to ask this instead; a Cell that came back after a
    reboot asks the same question and answers nothing, because the last thing
    said was the model's. So a restart never replays a conversation and an
    outstanding question is never dropped.

    False on an empty conversation, which is a chat nobody has started.
    """
    said = nu.List(_said(plane_id, cell_id, root))
    last = nu.Dict(nu.List(_said(plane_id, cell_id, root))[nu.Len(said) - nu.Int(1)])
    return nu.And(
        nu.Gt(nu.Len(said), nu.Int(0)),
        nu.Eq(
            nu.ToStr(last.get_item(nu.Str("role"), nu.Str(ROLE_SYSTEM))),
            nu.Str(ROLE_USER),
        ),
    )


def changed(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A fresh subscription that fires on every message.

    A read rather than a write, and the address is here for the same reason
    the writes are: two callers spelling one ref chain is two chances to spell
    it differently. Fresh at every call site, because two arms holding one
    subscription hold one handle and the first to end closes it under the
    other.

    **The Cell's state, not the leaf the conversation is in.** A leaf watch
    fires in the process that opened the store and never in a worker on the
    far end of the proxied change feed: it binds, it reports nothing, and a
    chat answers the message it came up holding and then goes deaf. A watch on
    the container above it carries.

    So this hears the display id too, which is written by the same press that
    writes the message and says nothing new. It no longer hears the trace at
    all: a turn narrates itself into the panel's state, on the Plane that
    draws, so the loop is not woken once a pass by a row it does not read.
    """
    return _own(plane_id, cell_id, root).on_change()


def trace_changed(
    disp_plane_id: nu.StrArg, disp_cell_id: nu.StrArg, *, root: type[Space] = Space
) -> nu.Nu:
    """A fresh subscription that fires on every row of one turn's trace.

    The display Cell's own state, which is the container the trace is a key
    in. A child scoped watch never carries to a worker, so the finest thing
    that can wake one is a Cell's own state, and nothing else is kept in this
    one: a panel drawing a turn is woken by that turn and by nothing else.

    Fresh at each call site, because a subscription is a handle: two arms
    sharing one node share one handle, and the first of them to end closes it
    under the other.

    Called with the panel's own two ids, so there is no empty id to guard
    against here the way the writes guard against one.
    """
    return _own(disp_plane_id, disp_cell_id, root).on_change()
