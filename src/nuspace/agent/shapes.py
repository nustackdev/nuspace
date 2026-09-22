"""The slots one turn runs on, and the one slot the model writes to finish.

nuagent's two Shapes, brought across and renamed for the words we use now.
``Session`` is a turn's working memory: the conversation the host is having
with the model, the raw reply, the source pulled out of it, what running that
came to, the observation fed back, how many passes have gone, and what the
answer cycle handed back. ``Run`` is the one slot the model owns.

**The session is on kv and only on kv.** nuagent ships a mem twin and the
difference is the whole of what separates an ephemeral run from a durable
one; here there is nothing to choose. A turn that kept its working memory in
a dict of its own kept it where nobody could look, which is exactly why a
chat went quiet for a minute: the model's sentences existed only inside the
worker that was about to throw them away. On kv they are in the store, so the
host can narrate out of them and a panel can draw them.

**``Run`` stays flat, untagged and on mem.** The model ends a cycle by
redeclaring that Shape in its own module and setting the slot, so a ``Run``
addressed anywhere but where a bare redeclaration reaches is a ``Run`` that
silently never ends anything. One slot, one meaning, written by the model and
read by the loop.
"""

from __future__ import annotations

import nu
import nustd.kv
import nustd.mem


__all__ = ["Run", "Session"]


class Session(nu.Shape):
    """One turn's working memory, durable and readable while it runs."""

    #: The conversation with the model, oldest first. Seeded with the opening
    #: at the top of a turn and appended to twice per pass.
    messages = nustd.kv.ListRef.slot(dict)

    #: The raw reply of the pass that just ran: prose, then a fenced block.
    reply = nustd.kv.StrRef.slot()

    #: The source pulled out of that block. What gets constructed and run.
    draft = nustd.kv.ProgramRef.slot()

    #: What running it came to. A yield, a construction diagnostic, a runtime
    #: error or a complaint about the answer all wear this one slot, because
    #: to the model they are one thing: the next thing to read.
    outcome = nustd.kv.StrRef.slot()

    #: The outcome and the world, as the message that goes back.
    observation = nustd.kv.StrRef.slot()

    #: How many passes this cycle has taken. Zeroed at the top of each cycle,
    #: so ``pass 2 of 8`` means the second pass of the cycle a reader is
    #: watching rather than the second of the turn.
    passes = nustd.kv.IntRef.slot()

    #: What the answer cycle's pass handed back: ``cell`` is the source of the
    #: Cell to draw and ``said`` is the line the conversation keeps. Empty
    #: through the whole work cycle.
    answer = nustd.kv.DictRef.slot(str)

    #: Whether the answer cycle has put a Cell on the screen. The cycle's exit,
    #: and the one thing the model cannot set: it hands back an answer and the
    #: host decides whether the answer stood up.
    drawn = nustd.kv.BoolRef.slot()


class Run(nu.Shape):
    """The cycle itself: set ``done`` and the work cycle stops.

    Notes:
        - ``done`` is the model's to write. Set it in the same program that
          finishes the work, once the work is actually finished.
        - The loop reads this exact slot after every pass. Nothing else ends a
          cycle except the pass budget.
        - It rides on the app's own fabric, so it needs no binding of its own.
    """

    done = nustd.mem.BoolRef.slot()
