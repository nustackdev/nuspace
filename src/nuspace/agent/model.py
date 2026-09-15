"""The model endpoint: a Claude Code prompt, fed the run's whole transcript.

nuagent's ``turn`` calls ``chat(messages=...)`` and expects a term yielding
``{"text": ...}``. ``nustd.llm`` speaks that natively but wants a provider and a
key; ``nustd.cc`` wants neither, and a space is a thing you run on your own
machine, so that is what is wired here. The cost is that each call is a fresh
Claude Code session, so the conversation has to ride along in the prompt --
which is what :class:`Rendered` is for.

The system prompt is prepended here rather than stored as message zero, and
that is load bearing twice over. It keeps several kilobytes of preamble out of
kv and off every frame the sidebar is shipped; and it means the transcript the
browser subscribes to is exactly the conversation, with no message a reader
has to be told to skip.

Same shape as nuagent's own ``examples/tracker.py``, which is where the
``ScalarQuery``-as-renderer idiom comes from: a python ``str.join`` in the
middle of a Nu tree would make the turn unwalkable, so the flattening is an
atom like everything else.

Named ``model`` rather than ``chat`` because :mod:`nuspace.chat` is the
conversation and this is the thing the run talks to. The transcript rendered
here is nuagent's working memory -- replies and observations -- and it is not
what the person reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.cc
from nu.lang import ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu
    from nu.lang.runtime import Runtime


__all__ = ["Bot", "Rendered", "chat_with"]


class Bot(nu.Service):
    """The Claude Code endpoint one space's agent runs against."""

    ask = nustd.cc.PromptRef.method()


class Rendered(ScalarQuery):
    """A ``[{role, content}]`` list flattened into one role-tagged prompt.

    The run's transcript, not :mod:`nuspace.chat`. Those are ``{role, text}``
    and hold what was said out loud; these are ``{role, content}`` and hold
    what the model and the host said to each other.

    Args:
        messages: the transcript, as a term. EMPTY on a store that has not
            been seeded yields INVALID, which is what stops a half-built
            prompt reaching the model rather than a silently empty one.
    """

    def __init__(self, messages: Nu) -> None:
        super().__init__(messages)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (messages,) = children

        def thunk(rt: Runtime) -> object:
            return _render(messages(rt))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (messages,) = children

        async def athunk(rt: Runtime) -> object:
            return _render(await messages(rt))

        return athunk


def _render(messages: object) -> object:
    """Role-tagged blocks, or INVALID for anything that is not a transcript.

    Duck-typed, and it has to be. A ``nustd.kv`` ``ListRef`` of dicts does not
    read back as ``list[dict]`` -- it reads back as a lazy sequence view whose
    elements are mapping views, live cursors into the store. An
    ``isinstance(messages, list)`` gate therefore rejected every real
    transcript, returned INVALID, and INVALID composed through the prompt
    string all the way down into the model call, where it surfaced as
    ``'Invalid' object is not iterable`` with nothing left to say where it came
    from. ``list()`` and ``dict()`` take the view and the builtin alike.

    Still total: anything genuinely unusable is INVALID rather than an
    exception, because this runs inside a turn and a raise here kills the run
    rather than feeding the model something it could fix.
    """
    if messages is EMPTY or messages is INVALID:
        return INVALID
    try:
        items = list(messages)  # type: ignore[call-overload]
    except TypeError:
        return INVALID
    blocks = []
    for message in items:
        try:
            record = dict(message)
        except (TypeError, ValueError):
            return INVALID
        role = str(record.get("role", "user")).upper()
        blocks.append(f"### {role}\n\n{record.get('content', '')}")
    return "\n\n".join(blocks)


def chat_with(system: str) -> Callable[..., Nu]:
    """A ``chat`` callable for nuagent's ``turn``, with ``system`` in front.

    Args:
        system: the system prompt. Constant for the life of the process, so it
            is composed in as a python string rather than read from anywhere.

    Returns:
        ``chat(*, messages)``, matching what ``turn`` calls.
    """
    preamble = nu.Str(system) + nu.Str("\n\n")

    def chat(*, messages: Nu) -> Nu:
        return Bot.ask(prompt=preamble + nu.Str(Rendered(messages)))

    return chat
