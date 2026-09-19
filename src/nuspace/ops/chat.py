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
"""

from __future__ import annotations

import nu
from nuspace.ops.utils import atomic
from nuspace.shapes import TRIGGER_BOOT, Space


__all__ = [
    "MESSAGES",
    "ROLES",
    "ROLE_AGENT",
    "ROLE_SYSTEM",
    "ROLE_USER",
    "changed",
    "messages_of",
    "say",
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


#: What the row reader binds the message it is on under. Parallel arms share
#: one ``ctx.attrs``, so it is namespaced to this module.
_ITEM = "_nx_said"
_item = nu.DictAttrRef(_ITEM)


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
    the container above it carries. Nothing else lives in a talking Cell's
    state, so the wider watch costs a turn nobody notices and every reader
    here is guarded on what was actually said.
    """
    return root.planes[plane_id].cells[cell_id].state.on_change()
