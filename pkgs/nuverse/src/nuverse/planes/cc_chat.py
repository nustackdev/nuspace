"""The ``cc_chat`` Plane: a chat with Claude Code, drawn as a plane of Cells.

Everything a chat does is in :mod:`nuspace.agent`. This Plane is the part
that is a choice: which model the chat talks to. It is named after that
backend, so a chat on another one is another Plane beside this one, made of
the same core.

A chat is born with one Cell, ``input``: a box and a send button. Pressing
send is :func:`nuspace.agent.chat.submit`, and the first press makes the
headless Plane that talks, nested under this one, with :data:`TALK` as its
one Cell. Every turn after that appends its panel, its answer and a folded
box under it, so the Plane reads top to bottom as the conversation.

The talking Cell's program is a few lines that call into the package, so a
newer nuspace upgrades every chat already in the store. It is spelled into
the input Cell's source rather than imported from here, the way Jobs spells
its starter in, so a chat's Cells stand on nuspace alone.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["INPUT", "PLANE", "TALK"]


#: The talking Cell's program. Claude Code, in one session for as long as the
#: chat is up, against the Plane this chat draws on, which the Plane that
#: talks reads off its own state.
TALK = """\
import nu
import nuspace.agent
from nuspace import ops
from nuspace.agent import chat
from nuspace.agent.cc import claude_code


def out():
    # One chat, live: answer whatever is outstanding, then wait for more. The
    # Plane it draws on is read once, in a snapshot that closes before it starts.
    plane, cell = ops.Here.plane, ops.Here.cell
    return nu.let(
        ops.snapshot(chat.drawn_of(plane)),
        lambda drawn: nuspace.agent.converse(
            plane, cell, ui_plane_id=nu.Str(drawn), talk=claude_code()
        ),
    )
"""


INPUT = (
    '''\
import nu
import nustd.ui
from nuspace import ops
from nuspace.agent import chat

#: What the first message makes the Plane that talks with.
TALK = """\\
'''
    + TALK
    + '''"""


class Box(nustd.ui.Column):
    message = nustd.ui.TextAreaRef.slot()
    send = nustd.ui.ButtonRef.slot(label="send")


def out():
    # The box is emptied after the submit and not before, because the submit
    # is what reads it.
    sent = chat.submit(ops.Here.plane, nu.Str(Box.message), talk=TALK) >> Box.message.set("")
    return (
        Box.message.set("")
        >> Box.send.set_label("send")
        >> nu.ReactForever(Box.send.on_click(), sent)
    )
'''
)


PLANE = Plane(
    "cc_chat",
    "CC chat",
    icon="message-square",
    description="Talk to Claude Code. It answers by writing Nu and drawing Cells.",
    meta={"editable": False, "full_width": False},
    cells=(("input", INPUT),),
    backend="async",
)
