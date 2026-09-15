"""The agent slot: one nuagent run, stored on the space.

``Agent`` is deliberately one shape and not two. nuagent's ``turn`` reads six
slots off whatever it is handed as ``session`` -- ``messages``, ``reply``,
``draft``, ``outcome``, ``observation``, ``turns`` -- and those are exactly
the slots a chat sidebar wants to show. Declaring them here, chained under
``Space.agent``, means the agent's working memory *is* the thing the browser
subscribes to, with no mirror to keep in step.

The rest is the submission half, which is nuspace's own:

``task``    what the human typed. Read at the start of a run and turned into
            the first user message.
``nonce``   bumped on every submit. **This** is what the runner subscribes to,
            not ``task``: asking the same question twice is a real thing to
            want and a change feed over the value alone cannot see it.
``status``  where the run is. The one field the surface is allowed to branch
            on, and the runner's own guard against a second submit landing
            mid-run.
``error``   what went wrong outside the model's repair loop. A construction
            failure is not this -- that is the model's input, and it lands in
            ``outcome`` like every other turn.

One run at a time, because nuagent is one run at a time. When that stops being
true this grows a ``ShapesDictRef`` keyed by run id and nothing else moves.

``KVRun`` is not used and neither is nuagent's ``Run``-on-the-session idea:
the model ends a run by writing ``Run.done``, which is ``nustd.mem`` and
addresses by slot name into the untagged store :mod:`nuspace.agent.runner`
provides around the loop. Keeping it off ``Agent`` is what keeps the model
from reaching the conversation.
"""

from __future__ import annotations

import nu
import nustd.kv


__all__ = [
    "DEFAULT_MAX_TURNS",
    "STATUS_DONE",
    "STATUS_FAILED",
    "STATUS_IDLE",
    "STATUS_RUNNING",
    "STATUS_STOPPED",
    "Agent",
]


#: Nothing has been asked, or the last run was cleared.
STATUS_IDLE = "idle"
#: A turn is in flight. The runner refuses a second submit while this holds.
STATUS_RUNNING = "running"
#: The model wrote ``Run.done``. It says the work is finished, nothing checked.
STATUS_DONE = "done"
#: The turn budget ran out first. Not an error, just an unfinished run.
STATUS_STOPPED = "stopped"
#: The loop itself raised. The model's own mistakes never reach here.
STATUS_FAILED = "failed"


#: Turns one submission gets. Small on purpose: a run that has not converged
#: in this many turns is usually a task that needed splitting, and an agent
#: editing a live space is cheaper to re-ask than to let wander.
DEFAULT_MAX_TURNS = 8


class Agent(nu.Shape):
    """One agent run: nuagent's session slots, plus how a human starts one."""

    # -- the submission, nuspace's own ---------------------------------------
    task = nustd.kv.StrRef.slot()
    nonce = nustd.kv.IntRef.slot()
    status = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()

    # -- nuagent's session contract, slot for slot ---------------------------
    messages = nustd.kv.ListRef.slot(dict)
    reply = nustd.kv.StrRef.slot()
    draft = nustd.kv.ProgramRef.slot()
    outcome = nustd.kv.StrRef.slot()
    observation = nustd.kv.StrRef.slot()
    turns = nustd.kv.IntRef.slot()
