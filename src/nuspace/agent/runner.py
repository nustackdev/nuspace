"""The agent runner: one submission, one nuagent loop, forever.

Space-wide and resident, like the apps supervisor and for the same reason:
there is one agent per space, it is not a thing a tab owns, and a run started
in one browser must be visible in every other. So it is mounted by
:func:`~nuspace.web.space.space_tree` beside the apps supervisor, not by a
connection's driver.

The shape of it is one arm:

    boot   blank the slot, so a process starts idle whatever the last one left
    arm    ``Agent.nonce`` changed -> run one nuagent loop to completion

``nonce`` rather than ``task``, because asking the same question twice is a
real thing to want and a change feed over the value cannot see it. The arm
still reads ``task`` before it runs, and refuses an empty one: the boot pass
writes ``nonce`` too, and its commit lands after the feed is open.

**Nothing here reaches into the web layer, and the web layer does not reach in
here.** The one exception is ``Arms``, which is how every nuspace driver builds
an arm and is imported inside the function rather than at module scope --
:mod:`nuspace.web.space` imports this module, so a top-level edge back would
make which of the two you reach for first decide whether the package imports.
A submit is a kv write through :mod:`nuspace.agent.ops`; the runner is
subscribed to the same store and hears it. That is the same separation the
apps runner has, and it is why "run this" is spelled "write the task" rather
than "tell the runner something".

Two fabrics are bracketed around the loop and the difference between them is
the whole security model:

- the space store is **already bound**, tagged by the root Shape class, by
  ``space_tree``'s head. The model reaches it by importing the real ``Space``.
- an untagged ``dict`` is provided **here**, and it is where ``nuagent.Run``
  lives. The model writes ``Run.done`` into it to end the run, and any
  ``nustd.mem`` scratch it invents lands there too, out of the way.

``Agent`` carries the session slots, so the conversation is in kv and the
sidebar subscribes to it directly. It is handed to nuagent as ``session``
unchanged -- ``Space.agent.messages`` is a Ref like ``MemSession.messages`` is
a Ref, and nuagent never asked for more than that.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nuagent

import nu
import nustd.cc
import nustd.kv
from nuspace._root import resolve_root
from nuspace.apps import ops as apps_ops
from nuspace.chat import ops as chat_ops
from nuspace.pages import ops as pages_ops

from . import ops
from .model import Bot, chat_with
from .prompt import system_prompt
from .shapes import DEFAULT_MAX_TURNS, STATUS_DONE, STATUS_FAILED, STATUS_RUNNING, STATUS_STOPPED


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.domains.shape import Shape


__all__ = ["DEFAULT_MODEL", "agent_runner"]


#: What the loop talks to when nobody says otherwise. Claude Code rather than
#: an api key, because a space runs on the machine the person is sitting at.
DEFAULT_MODEL = "claude-opus-4-5"


#: The arm's attrs namespace, and what a failure is reported as.
_RUN = "agent_run"


#: What the host says when the turn budget ran out. The host speaks here and
#: nowhere else: a run that ended without the model appending anything is
#: silence in the sidebar, and silence reads as a broken space rather than as
#: an unfinished job. It is tagged `system` and it is about the *run* -- what
#: the work amounted to stays the agent's to report, and it did not.
BUDGET_GONE = "Ran out of turns before finishing. Ask again, or ask for less."

#: Same, for the loop itself dying. The model's own mistakes never reach this:
#: a module that will not construct is fed back to it and the run carries on.
CRASHED = "The run crashed and stopped: "


def agent_runner(
    *,
    root: type[Shape] | None = None,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    echo: bool = True,
    chat: Callable[..., nu.Nu] | None = None,
    bind: nu.Nu | None = None,
) -> nu.Nu:
    """The agent, live, as one tree. One per process, not one per connection.

    Args:
        root: the space's root Shape class. Also what the model is told about.
        model: the Claude Code model the loop runs against. Ignored when
            ``bind`` is passed.
        max_turns: the budget one submission gets.
        echo: print each turn's reply and observation on the server's stdout.
            The sidebar shows the same thing, but a run that dies between
            frames is only legible in the log.
        chat: the endpoint, as ``chat(*, messages) -> Nu`` yielding
            ``{"text": ...}``. Claude Code by default. Pass one to point a
            space at ollama or an api key instead -- or at a stub, which is
            what makes the wiring testable without spending a model call.
        bind: the bracket that provides whatever ``chat`` addresses. Must be
            passed with ``chat``: the default pair is ``nustd.cc.bind(Bot, ...)``
            and a Service endpoint with nothing provided for it is a
            ``LookupError`` on the first turn, not at boot.

    Returns:
        The tree. It never finishes, which is the contract everything that
        folds it holds it to.
    """
    # Deferred, and this is the one edge that would close a cycle: `web.space`
    # imports this module to mount the runner, so naming `nuspace.web` at
    # import time here makes which module you reach for first decide whether
    # the package imports at all. Same reason `nuspace._root` exists.
    from nuspace.web.arms import Arms

    arms = Arms("agent")

    root = resolve_root(root)
    agent = root.agent
    if chat is None:
        chat = chat_with(system_prompt(root))
    if bind is None:
        bind = nustd.cc.bind(Bot, model=model, allowed_tools=[], permission_mode="default")

    loop = nuagent.agent(
        # `Space.agent` is the session: the six slots nuagent reads are
        # declared on `Agent`, so its working memory is the store the browser
        # is already subscribed to and there is no mirror to keep in step.
        session=agent,
        run=nuagent.Run,
        chat=chat,
        state=_state(root),
        max_turns=max_turns,
        # The task is read here, at run time, and becomes message one. Seeding
        # it as a python string would pin the tree to whichever question
        # happened to be in the store when the process booted.
        start=agent.messages.set(nu.List.of(nu.Dict.of(role="user", content=agent.task))),
        echo=echo,
    )

    # The model's own mistakes never reach the catch: a module that does not
    # construct, or constructs and raises, is fed back to it as the next user
    # message and the run carries on. What lands here is the loop itself
    # failing -- the model endpoint unreachable, the store gone -- which ends
    # the run and has to be said out loud rather than leaving `running` set.
    attempt = nu.TryCatch(
        loop
        >> nu.IfDo(nu.Not(nuagent.Run.done), chat_ops.say_system(BUDGET_GONE, root=root))
        >> ops.set_status(nu.If(nuagent.Run.done, STATUS_DONE, STATUS_STOPPED), root=root),
        catch=ops.set_error(nu.ToStr(nu.AttrRef("error")), root=root)
        >> chat_ops.say_system(nu.Str(CRASHED) + nu.ToStr(nu.AttrRef("error")), root=root)
        >> ops.set_status(STATUS_FAILED, root=root),
    )

    # Two guards, and both earn their place.
    #
    # `task` non-empty is what makes the boot pass safe. The arm subscribes to
    # `nonce`, and `init_agent` writes `nonce` -- under `auto_flow_atomic` the
    # boot writes commit after the subscription is open, so the feed hears the
    # blanking and a cold process asked a model an empty question. There is no
    # ordering fix for that: the guard is to notice that a blank slot is not a
    # question. Every real submit sets `task` before it bumps `nonce`.
    #
    # `not running` drops a second submit landing mid-run rather than folding
    # it into the conversation it would be interrupting. `ops.submit` guards
    # the same way on the way in; this is the one that actually holds, because
    # it is the one inside the arm.
    once = nu.IfDo(
        nu.And(nu.Not(ops.running(root=root)), nu.Len(ops.task_of(root=root)) > nu.Int(0)),
        ops.set_status(STATUS_RUNNING, root=root) >> ops.set_error("", root=root) >> attempt,
    )

    boot = ops.init_agent(root=root)
    arm = arms.event(_RUN, agent.nonce.on_change(), once)

    return nu.With(
        # Untagged, so `nuagent.Run` -- and any nustd.mem the model invents --
        # resolves here and nowhere near the conversation.
        nu.Provide(dict, {}),
        bind,
        body=nustd.kv.auto_flow_atomic(boot >> arm, scope=root),
    )


def _state(root: type[Shape]) -> nu.Nu:
    """What the model is shown of the world after each of its programs ran.

    Ids only for the two containers, deliberately. nuagent appends this to
    every observation, so a full page-and-section dump would be re-sent once
    per turn and would crowd out the outcome it is supposed to be context for.
    The ids say what exists; reading one is a program the model can write.

    The conversation is the exception and goes in whole. It is the one piece
    of the world the model has to see verbatim: it is what it was asked, and
    it is the only record of what it has already said out loud. A model that
    could not read it back would re-append the same answer on a retried turn,
    or finish a run having said nothing and not be able to tell.
    """
    return nu.Dict.of(
        pages=pages_ops.page_ids(root=root),
        apps=apps_ops.app_ids(root=root),
        chat=chat_ops.messages_of(root=root),
    )
