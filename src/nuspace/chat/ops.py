"""Write + read primitives over the conversation.

Same rule as every other ops module here: each one returns a Nu tree, so the
web driver, a script, a cron job or the agent itself composes them rather than
hand-writing ref chains.

Write:
- :func:`init_chat` -- the container, once, on a cold store.
- :func:`say`       -- append one message. The only write there is.
- :func:`clear`     -- drop the conversation.

Read:
- :func:`messages_of` -- the whole thing, which is what the sidebar is.
- :func:`last_of`     -- the most recent message's text.

:func:`say` is deliberately the whole write surface. There is no edit and no
delete-one: a conversation is a log, and a participant that could rewrite what
it said earlier would make the transcript stop being evidence of what happened.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace._root import resolve_root

from .shapes import ROLE_AGENT, ROLE_SYSTEM, ROLE_USER


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "clear",
    "init_chat",
    "last_of",
    "messages_of",
    "say",
    "say_agent",
    "say_system",
    "say_user",
]


#: The name ``Map`` binds the current message under.
_ITEM = "_ch_item"


def _chat(root: type[Shape] | None) -> nu.Nu:
    """The ``Space.chat`` ref, for whichever root this call addresses."""
    return resolve_root(root).chat


# --- write -----------------------------------------------------------------


def init_chat(*, root: type[Shape] | None = None) -> nu.Nu:
    """Create the message list if the store has none. Idempotent.

    A subscription over a missing container resolves to INVALID and silently
    never fires, so anything meaning to watch the conversation boots through
    here first. ``List.create()``, not ``[]``: a literal is captured once at
    Form construction and shared across every evaluation of the term.
    """
    return _chat(root).messages.init(nu.List.create())


def say(role: nu.StrArg, text: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Append one message.

    Args:
        role: who is speaking -- ``user``, ``agent`` or ``system``. Not
            validated: an unknown role renders as ``system`` rather than
            disappearing, and a store that refused one would be a store that
            can lose a message.
        text: what was said, verbatim.
        root: the space's root Shape class.
    """
    return _chat(root).messages.append(nu.Dict.of(role=nu.Str(role), text=nu.Str(text)))


def say_user(text: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """A person said it. What the sidebar's composer writes."""
    return say(ROLE_USER, text, root=root)


def say_agent(text: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """The agent said it.

    Here for symmetry and for scripts. The agent itself does not call this --
    it writes the ``append`` into the program it emits, which is the same
    write, and going through a python helper would mean the host chose the
    words.
    """
    return say(ROLE_AGENT, text, root=root)


def say_system(text: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """The host said it, about the run rather than about the work."""
    return say(ROLE_SYSTEM, text, root=root)


def clear(*, root: type[Shape] | None = None) -> nu.Nu:
    """Drop every message."""
    return _chat(root).messages.set(nu.List.of())


# --- read ------------------------------------------------------------------


def messages_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """The conversation, one ``{role, text}`` dict per message, oldest first.

    Rebuilt key by key rather than handed over as it lies. A ``ListRef`` of
    dicts reads back as a list of kv *views*, and a view is a live cursor into
    the store, not a value -- msgpack cannot serialise one, so shipping the
    bare list is a frame that fails on the way out and an arm that reports
    itself once per write.
    """
    return nu.Collect(
        nu.Map(
            nu.list(_chat(root).messages),
            nu.Dict.of(
                role=nu.ToStr(nu.DictAttrRef(_ITEM).get_item(nu.Str("role"), nu.Str(ROLE_SYSTEM))),
                text=nu.ToStr(nu.DictAttrRef(_ITEM).get_item(nu.Str("text"), nu.Str(""))),
            ),
            key=_ITEM,
        )
    )


def last_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """The most recent message's text, or ``""`` on an empty conversation."""
    messages = nu.list(_chat(root).messages)
    return nu.ToStr(
        nu.If(
            nu.Len(messages) > nu.Int(0),
            nu.Dict(nu.List(messages)[nu.Int(nu.Len(messages)) - nu.Int(1)]).get_item(
                nu.Str("text"), nu.Str("")
            ),
            nu.Str(""),
        )
    )
