"""One pass: one model call, plus the program it wrote.

The smallest thing a cycle is made of, and the reason the agent came into
nuspace. nuagent composes this same sequence and hands back one opaque Flow,
which is fine for an agent nobody is watching and wrong for a chat: a person
is looking at the screen for the whole of it, and every link in the chain is
something they would want to see happen.

So the chain is written out, with :class:`~nuspace.agent.trace.Panel` rows in
between:

    thinking  ->  ask  ->  record  ->  extract  ->  writing  ->  act
              ->  repeated?  ->  running or failed  ->  observe  ->  record

**The states are written between the links and not around them.** A row after
the whole pass would arrive with everything else at the end, which is the
failure this replaces.

**The middle link is the cycle's.** Everything else is the same in both
cycles, and what differs is what the model's program is *for*: in the work
cycle it acts on the space, in the answer cycle it hands back a Cell to draw.
That one term is passed in as ``act``, and it is the only seam.

**One link is bookkeeping and it is here because it is per pass.**
:func:`_repeated` is what a cycle's guard reads: whether this pass failed the
same way the last one did. It sits right after ``act``, because ``act`` is
what wrote the outcome it looks at, and before the row, so a panel and a loop
are never a pass apart on the same question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace.agent import source, trace


if TYPE_CHECKING:
    from collections.abc import Callable

    from nuspace.agent.trace import Panel


__all__ = ["OBSERVED", "STATED", "one"]


#: What the observation calls the yield of the program that just ran.
OBSERVED = "outcome: "

#: And what it calls the world underneath it.
STATED = "\nstate: "


def one(
    *,
    session: nu.Nu,
    panel: Panel,
    ask: Callable[..., nu.Nu],
    cycle: str,
    act: nu.Nu,
    budget: nu.IntArg,
    state: nu.Nu | None = None,
) -> nu.Nu:
    """Compose one pass of a cycle, with the host's rows between the links.

    Args:
        session: the turn's slots, as the ref they hang off.
        panel: where this turn's rows go.
        ask: what reaches the model. Called with ``messages=`` and yields a
            dict with ``text`` in it. Handed in rather than chosen here,
            because which model a chat talks to is the endpoint's business and
            a pass is the same either way.
        cycle: which cycle this pass belongs to, written on every row it
            leaves. One of :data:`nuspace.ops.chat.CYCLES`.
        act: what to do with the source the model wrote. Sets ``outcome``,
            whatever happens, because ``outcome`` is what the model reads next.
        budget: how many passes the cycle gets, written after the count. A
            term rather than a number wherever it is a fact about the chat, so
            a ceiling raised mid run shows up on the next row.
        state: the world after the program ran, appended to the observation.
            Omitted for a cycle whose model has nothing to look at.

    Returns:
        A Flow: one pass, ready to run under a ``WhileDo``.

    Notes:
        - The counter goes up at the head of the pass rather than at the foot,
          so ``pass 1 of 8`` is the pass a reader is watching rather than the
          one that just ended.
        - Nothing is truncated on the way to the model. A model shown half a
          list it just wrote cannot tell a landed append from a failed one, so
          it appends again and the observation grows. What the panel shows is
          cut; what the model reads is not.
    """
    messages = session.messages
    reply = session.reply
    draft = session.draft
    outcome = session.outcome
    observation = session.observation

    observed = nu.Str(OBSERVED) + nu.Str(outcome)
    if state is not None:
        observed = observed + nu.Str(STATED) + nu.ToStr(nu.Repr(state))

    return (
        # Before the call and not after it. A model call is one atom with no
        # inside, so this is the last moment anything can reach the panel
        # before the person starts waiting.
        panel.thinking(cycle)
        >> reply.set(nu.Str(nu.dict(ask(messages=messages))["text"]))
        >> messages.append(nu.Dict.of(role="assistant", content=reply))
        >> draft.set(source.fenced(reply))
        >> session.passes.inc()
        >> panel.writing(cycle, budget=budget)
        >> act
        >> _repeated(session)
        >> panel.ran(cycle)
        >> observation.set(nu.Str(observed))
        >> messages.append(nu.Dict.of(role="user", content=observation))
    )


def _repeated(session: nu.Nu) -> nu.Nu:
    """Count this pass against the last one, and keep what it failed at.

    The whole of the stall guard, and it is deliberately the narrowest thing
    that tells the two cases apart. A model failing in new ways is working:
    each diagnostic is different because each one is further in. A model
    handed back the same first line three times has stopped reading it, and no
    number of further passes changes that.

    Only a complaint counts. The yield of a program that worked is not
    evidence of anything: a pass that writes yields nothing at all, so a run
    of honest write passes all report the same thing and would look like a
    spin. What is compared is the first line, because that is where the label
    and the message are and everything under it is a traceback that moves.
    """

    def line() -> nu.Nu:
        """The head of what the pass came to. Fresh at each call site."""
        return trace.head(nu.Str(session.outcome))

    return nu.IfDo(
        source.complaint(line()),
        nu.IfDo(
            nu.Eq(line(), nu.Str(session.failure)),
            session.repeats.inc(),
            session.repeats.set(nu.Int(1)) >> session.failure.set(line()),
        ),
        session.repeats.set(nu.Int(0)) >> session.failure.set(nu.Str("")),
    )
