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

:func:`submit` is the one op here that reaches past the conversation. A chat
is made at ``trigger: manual`` and the first message is what starts it, so the
append and the flip land in one commit or a chat is observable holding a
question with nothing running to answer it.

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

``steps`` is the third thing kept here and the shortest lived: what the agent
is doing while it is doing it, the host's write, thrown away when the next
turn starts. It is beside ``messages`` because it is about the same run and a
caller holding the chat's address already holds it, and it is a list of its
own because it is not the conversation. Nobody said any of it, and a person
reading back next week wants none of it.
"""

from __future__ import annotations

import nu
from nuspace.ops.cell import add_cell
from nuspace.ops.utils import atomic
from nuspace.shapes import RESTART_NO, TRIGGER_BOOT, Space


__all__ = [
    "MESSAGES",
    "ROLES",
    "ROLE_AGENT",
    "ROLE_SYSTEM",
    "ROLE_USER",
    "STEPS",
    "STEP_DONE",
    "STEP_DREW",
    "STEP_FAILED",
    "STEP_KINDS",
    "STEP_THINKING",
    "STEP_WROTE",
    "changed",
    "clear_steps",
    "draw",
    "messages_of",
    "say",
    "step",
    "steps_changed",
    "steps_of",
    "submit",
    "unanswered",
]


#: The key the conversation is kept under, in the talking Cell's own state.
MESSAGES = "messages"

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


#: The key the run log is kept under, in that same state.
STEPS = "steps"

#: It is working, and has nothing to show for it yet.
STEP_THINKING = "thinking"

#: It put a Cell on the Plane that draws the chat.
STEP_DREW = "drew"

#: It changed the Space: a Plane, a Cell, a program. Every write that is not
#: a drawing.
STEP_WROTE = "wrote"

#: Something in the turn went wrong. About the run, never about the work,
#: which is the model's to report.
STEP_FAILED = "failed"

#: The turn is over. The last step a turn takes, and what tells a reader the
#: list in front of it is finished rather than stalled.
STEP_DONE = "done"

#: Every kind a reader knows, and a closed set because a step is drawn *by*
#: its kind: one shape per kind is the whole of what makes the panel uniform,
#: and a kind nobody knows has no shape to draw. Anything else reads as
#: ``thinking``, which is the kind that claims the least.
STEP_KINDS = (STEP_THINKING, STEP_DREW, STEP_WROTE, STEP_FAILED, STEP_DONE)


#: What the row reader binds the message it is on under. Parallel arms share
#: one ``ctx.attrs``, so it is namespaced to this module.
_ITEM = "_nx_said"
_item = nu.DictAttrRef(_ITEM)

#: The same for a step, and a second name rather than the one above. One Cell
#: can draw the conversation and the run log in two parallel arms, and two
#: Maps binding one attr would each be reading the other's element.
_STEP_ITEM = "_nx_step"
_step_item = nu.DictAttrRef(_STEP_ITEM)


def _held(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The leaf the conversation is kept in.

    A fresh ref at every call site. One node in two tree positions is one
    node, and a subscription is a handle the first holder to end would close
    under the other.
    """
    return root.planes[plane_id].cells[cell_id].state[MESSAGES]


def _said(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The conversation as it lies, empty where nothing has been said.

    Floored, because an unwritten leaf reads EMPTY and every Query touching
    EMPTY collapses to INVALID, which writes nothing and raises nothing.
    """
    held = _held(plane_id, cell_id, root)
    return nu.If(held.exists(), nu.List(held), nu.List.of())


def _kept(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The leaf the run log is kept in.

    Fresh at every call site for the reason :func:`_held` is, and beside it
    rather than under it: one leaf per list, so clearing the steps at the top
    of a turn cannot reach the conversation.
    """
    return root.planes[plane_id].cells[cell_id].state[STEPS]


def _taken(plane_id: nu.StrArg, cell_id: nu.StrArg, root: type[Space]) -> nu.Nu:
    """The steps as they lie, empty where the turn has taken none.

    Floored like :func:`_said`, and a chat spends most of its life here: the
    leaf is unwritten until the first turn clears it, and an unwritten leaf
    reads EMPTY, which collapses every Query that touches it to INVALID.
    """
    kept = _kept(plane_id, cell_id, root)
    return nu.If(kept.exists(), nu.List(kept), nu.List.of())


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
            would be a store that can lose a message.
        text: what was said, verbatim.
        root: the Space shape class.
    """
    cells = root.planes[plane_id].cells
    state = cells[cell_id].state
    return atomic(
        nu.IfDo(
            cells.contains(cell_id),
            state.set_item(
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
    root: type[Space] = Space,
) -> nu.Nu:
    """A person said something, and the first thing they say starts the chat.

    Two facts in one commit, which is why this is an op rather than two. A
    chat is made at ``trigger: manual``, so nothing is running behind it until
    somebody talks; the first message flips the Plane to ``boot`` and the
    runtime brings it up. Every message after that only appends, because the
    Plane is already up and hears the write.

    The emptiness test comes first in the sequence and that is load bearing: a
    Transaction sees its own writes, so asking after the append would always
    answer no and a chat would never start.

    Empty text is dropped rather than appended. A submit with nothing in it is
    a stray click, and a chat that started on one would ask a model an empty
    question.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
        text: what the person wrote.
        root: the Space shape class.
    """
    plane = root.planes[plane_id]
    state = plane.cells[cell_id].state
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
            >> state.set_item(
                MESSAGES,
                nu.List(_said(plane_id, cell_id, root))
                + nu.List.of(nu.Dict.of(role=nu.Str(ROLE_USER), text=nu.Str(text))),
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


def step(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    kind: nu.StrArg,
    text: nu.StrArg,
    *,
    root: type[Space] = Space,
) -> nu.Nu:
    """Record one thing the agent did on the way to an answer.

    Not a message, and the difference is who it is for. A message was said to
    somebody and is kept forever, which is why nothing edits or drops one. A
    step is the agent narrating itself while the turn runs: the host writes
    it, the next turn throws it away, and somebody reading the conversation
    back later should see none of it.

    Appends rather than replaces, so a slow turn reads as a list that grows
    instead of one line that flickers.

    Guarded on the Cell for the reason :func:`say` is: a write under a key
    nobody made vivifies the row, and a chat deleted mid turn would grow a
    Cell out of a late step.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
        kind: one of :data:`STEP_KINDS`, which is what a reader draws it by.
            Not validated, for the reason a role is not: an unknown kind reads
            as ``thinking`` rather than disappearing, and a store that refused
            one would be a store that can lose what happened.
        text: what to show for it, in one line.
        root: the Space shape class.
    """
    cells = root.planes[plane_id].cells
    state = cells[cell_id].state
    return atomic(
        nu.IfDo(
            cells.contains(cell_id),
            state.set_item(
                STEPS,
                nu.List(_taken(plane_id, cell_id, root))
                + nu.List.of(nu.Dict.of(kind=nu.Str(kind), text=nu.Str(text))),
            ),
        ),
        root,
    )


def clear_steps(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Throw away the steps, so a turn starts on a clean list.

    At the top of a turn and not at the bottom, which is the difference
    between a panel a person can read and one that blanks. What the last turn
    did stays up until the next turn has something of its own to show.

    Written empty rather than erased: an erase on a leaf nothing wrote raises,
    and every chat's first turn clears before it has ever stepped.

    Guarded on the Cell, because a write under a key nobody made makes one.
    """
    cells = root.planes[plane_id].cells
    return atomic(
        nu.IfDo(cells.contains(cell_id), cells[cell_id].state.set_item(STEPS, nu.List.of())),
        root,
    )


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


def steps_of(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """What the agent is doing, one ``{kind, text}`` dict each, oldest first.

    Rebuilt key by key rather than handed over as it lies, for the reason
    :func:`messages_of` is: a list written into a kv leaf reads back as a
    *view*, and a view is a live cursor into the store rather than a value, so
    the bare list is a frame msgpack cannot pack and an arm that reports
    itself once per write. The Cell drawing this redraws on every step, which
    is the one place that failure would show up most.

    A step with nothing under ``kind`` floors to ``thinking`` rather than
    dropping out of the list: it is still something that happened, and that is
    the kind which says the least about it. A kind nobody knows comes through
    as it was written, for the same reason an invented role does, and it is
    the reader that decides what an unknown one looks like.
    """
    return nu.Collect(
        nu.Map(
            nu.List(_taken(plane_id, cell_id, root)),
            nu.Dict.of(
                kind=nu.ToStr(_step_item.get_item(nu.Str("kind"), nu.Str(STEP_THINKING))),
                text=nu.ToStr(_step_item.get_item(nu.Str("text"), nu.Str(""))),
            ),
            key=_STEP_ITEM,
        )
    )


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

    So this hears the steps too, because those are in that same state. Every
    reader here re-asks what was actually said, so a wake on a step is a turn
    round a loop that finds nothing owed and goes back to waiting.
    """
    return root.planes[plane_id].cells[cell_id].state.on_change()


def steps_changed(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """A fresh subscription that fires on every step.

    The same container :func:`changed` watches, and named twice on purpose. A
    child scoped watch never carries to a worker, so the finest thing that can
    wake one is the Cell's own state, and that one container holds both lists.
    Two names because the two callers are asking two questions and neither
    should be spelling a ref chain of its own, and because a subscription is a
    handle either way: two arms sharing one node share one handle, and the
    first of them to end closes it under the other.
    """
    return root.planes[plane_id].cells[cell_id].state.on_change()
