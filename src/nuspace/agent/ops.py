"""Write + read primitives over the agent slot.

Same rule as :mod:`nuspace.apps.ops` and :mod:`nuspace.pages.ops`: every one
returns a Nu tree and nothing else, so the web driver, a script or another
agent compose them instead of hand-writing ref chains.

Write:
- :func:`init_agent` -- blank every slot. Run once per process, at boot.
- :func:`submit`     -- the human asked something. Task in, nonce up.
- :func:`reset`      -- forget the transcript, back to idle.
- :func:`set_status` / :func:`set_error` -- the runner's own bookkeeping.

Read:
- :func:`status_of` / :func:`task_of` / :func:`turns_of` / :func:`error_of`.
- :func:`messages_of` -- the whole transcript, which is what the sidebar is.
- :func:`running` -- whether a run is in flight, as a term.

What is *not* here is the conversation. That is :mod:`nuspace.chat`, and the
split is the point: this module is a run -- one task, its status, nuagent's
working memory for it -- while what was actually said to the person lives on
the agent's own surface and gets there because the model emitted a program
that appended to it. ``submit`` and ``reset`` reach across, because asking and
starting over are both things that happen to a conversation and to a run at
once.

``init_agent`` blanks rather than probes, and that is the honest thing here
rather than a shortcut. The loop lives in the space process, so a restart
already killed whatever was running; a store that still says ``running`` is
describing a process that is gone. Booting to ``idle`` says the true thing.
The run's own memory goes with it, because half a transcript whose next turn
will never come is worse than none. The conversation does not: it is a record
of what happened, and that stays true across a restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace._root import resolve_root
from nuspace.chat import ops as chat_ops

from .shapes import STATUS_IDLE, STATUS_RUNNING


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "error_of",
    "init_agent",
    "messages_of",
    "reset",
    "running",
    "set_error",
    "set_status",
    "status_of",
    "submit",
    "task_of",
    "turns_of",
]


#: The name ``Map`` binds the current message under. Read as a dict, not as
#: ``AnyAttrRef``: a message is a mapping and the item verbs live on the typed
#: ref, so the untyped one has no ``get_item`` to call.
_ITEM = "_ag_item"


def _agent(root: type[Shape] | None) -> nu.Nu:
    """The ``Space.agent`` ref, for whichever root this call addresses."""
    return resolve_root(root).agent


# --- write -----------------------------------------------------------------


def init_agent(*, root: type[Shape] | None = None) -> nu.Nu:
    """Blank every slot. What a process boots the agent into.

    ``nonce`` is blanked with the rest, which is safe because the runner
    subscribes *after* this runs: a change feed that is not open yet cannot
    hear the write that opens it.
    """
    agent = _agent(root)
    return (
        # The conversation survives a restart; the run does not. So this seeds
        # the chat container and blanks the run, which is the honest pair: a
        # transcript is a record of what happened and stays true, while a slot
        # still reading `running` would be describing a process that is gone.
        chat_ops.init_chat(root=root)
        >> agent.task.set(nu.Str(""))
        >> agent.nonce.set(nu.Int(0))
        >> agent.status.set(nu.Str(STATUS_IDLE))
        >> agent.error.set(nu.Str(""))
        >> agent.messages.set(nu.List.of())
        >> agent.reply.set(nu.Str(""))
        >> agent.outcome.set(nu.Str(""))
        >> agent.observation.set(nu.Str(""))
        >> agent.turns.set(nu.Int(0))
    )


def submit(text: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Ask the agent something. A no-op while a run is in flight.

    Two writes to two slots, and they are two things. The message goes into
    :mod:`nuspace.chat` because it was *said*, and it is the same append the
    agent will use to answer -- one log, both participants. The task goes onto
    ``Agent`` because it is what the run is *for*, and the run reads it there.

    Nonce last: it is what the runner watches, so bumping it after both have
    landed is what keeps a run from reading the previous question, or from
    starting before its own message is in the log.

    Args:
        text: the prompt, verbatim.
        root: the space's root Shape class.
    """
    agent = _agent(root)
    return nu.IfDo(
        nu.Not(running(root=root)),
        chat_ops.say_user(text, root=root) >> agent.task.set(nu.Str(text)) >> agent.nonce.inc(),
    )


def reset(*, root: type[Shape] | None = None) -> nu.Nu:
    """Drop the conversation and the run both, back to idle.

    A no-op while a run is in flight. Clears :mod:`nuspace.chat` as well as the
    run's own memory: the sidebar's one control means "start over", and a
    conversation left standing next to a blanked run is a transcript whose
    replies no longer have anything behind them.

    Not the same call as :func:`init_agent`: this one leaves ``nonce`` alone.
    Resetting is not asking, and a nonce that moved here would start a run on
    a task the human just cleared.
    """
    agent = _agent(root)
    return nu.IfDo(
        nu.Not(running(root=root)),
        chat_ops.clear(root=root)
        >> agent.task.set(nu.Str(""))
        >> agent.status.set(nu.Str(STATUS_IDLE))
        >> agent.error.set(nu.Str(""))
        >> agent.messages.set(nu.List.of())
        >> agent.reply.set(nu.Str(""))
        >> agent.outcome.set(nu.Str(""))
        >> agent.observation.set(nu.Str(""))
        >> agent.turns.set(nu.Int(0)),
    )


def set_status(status: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Say where the run is. The runner is the only writer."""
    return _agent(root).status.set(nu.Str(status))


def set_error(message: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Record what killed the loop. ``""`` clears it."""
    return _agent(root).error.set(nu.Str(message))


# --- read ------------------------------------------------------------------


def status_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """Where the run is, as a string. ``""`` on a store that never booted."""
    return nu.ToStr(_agent(root).status)


def task_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """The prompt the current run is answering."""
    return nu.ToStr(_agent(root).task)


def error_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """What killed the last loop, or ``""``."""
    return nu.ToStr(_agent(root).error)


def turns_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """How many turns the current run has spent."""
    return nu.ToInt(_agent(root).turns)


def messages_of(*, root: type[Shape] | None = None) -> nu.Nu:
    """The whole transcript, one ``{role, content}`` dict per message.

    Rebuilt key by key rather than handed over as it lies. A ``ListRef`` of
    dicts reads back as a list of kv *views*, and a view is a live cursor into
    the store, not a value -- msgpack cannot serialise one, so shipping the
    bare list is a frame that fails on the way out and an arm that reports
    itself once per write. ``Map`` over ``Dict.of`` copies the two keys the
    surface actually shows, which is both the fix and the truthful frame.

    The system prompt is not in here and never was: it is a python constant
    the chat adapter prepends per call, so the store holds the conversation
    and not the several kilobytes of preamble in front of it. See
    :mod:`nuspace.agent.chat`.
    """
    return nu.Collect(
        nu.Map(
            nu.list(_agent(root).messages),
            nu.Dict.of(
                role=nu.ToStr(nu.DictAttrRef(_ITEM).get_item(nu.Str("role"), nu.Str("user"))),
                content=nu.ToStr(nu.DictAttrRef(_ITEM).get_item(nu.Str("content"), nu.Str(""))),
            ),
            key=_ITEM,
        )
    )


def running(*, root: type[Shape] | None = None) -> nu.Nu:
    """Whether a run is in flight, as a term.

    Read off the store rather than off a ``nu.mem`` record, unlike the apps
    runner's ``attached``. An agent run is a fact about the space, not about
    the process: the browser has to see it, and it is the same answer for
    every connection.
    """
    return nu.Eq(status_of(root=root), nu.Str(STATUS_RUNNING))
