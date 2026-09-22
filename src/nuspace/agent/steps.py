"""What the agent is doing, written down while it is doing it.

A run takes as long as it takes, and until it ends the person has nothing to
look at: the answer is one program at the very end, and nothing before that
is visible anywhere. So a run narrates itself into
:func:`nuspace.ops.chat.step`, and the Cell a chat is seeded with draws the
list live.

**Two writers, and the split is about who knows.** The host owns the edges of
a run and writes them here: a run started, it ended, it ended without an
answer, it died. The model owns everything between, because what a program
was *for* is known only to whoever wrote it, and "renamed the Notes plane"
is a sentence no host can compose out of a term it did not author. That half
is taught in the prompt rather than written here.

That split is also the only one on offer. A turn of nuagent's has no hook in
the middle of it: everything it takes is either a term that has to yield a
value, which cannot also write, or a term that runs once around the whole
loop. So the host writes at the two places it actually stands.

The texts are constants rather than inline literals for the ordinary reason:
they are read by a person in a panel, they get reworded, and a reworded line
is a line somebody has to find.
"""

from __future__ import annotations

import nu
from nuspace.ops import chat
from nuspace.shapes import Space


__all__ = [
    "CRASHED",
    "ENDED",
    "STALLED",
    "STARTED",
    "crashed",
    "ended",
    "stalled",
    "started",
]


#: The first line of every run. It says the agent has the question and has
#: not answered it yet, which is all that is true at that moment.
STARTED = "reading what you said"

#: The last line of a run that answered. A reader needs it: without a closing
#: step a finished list and a stalled one look the same.
ENDED = "answered"

#: A run that used its turns without appending anything. About the run, never
#: about the work, which is the model's to report.
STALLED = "that run ended without an answer"

#: The loop itself dying, with the error after it. The model's own mistakes
#: never reach this: a module that will not construct is fed back to it and
#: the run carries on.
CRASHED = "the run crashed: "


def started(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Begin a run's list: throw the last one away, then say what this one has.

    Cleared at the top of a run and never at the bottom, which is the
    difference between a panel a person can read and one that blanks. What
    the last run did stays up until this one has something of its own.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
        root: the Space shape class.
    """
    return chat.clear_steps(plane_id, cell_id, root=root) >> chat.step(
        plane_id, cell_id, chat.STEP_THINKING, STARTED, root=root
    )


def ended(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Close a run's list. The run answered, and there is nothing more coming."""
    return chat.step(plane_id, cell_id, chat.STEP_DONE, ENDED, root=root)


def stalled(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Close a run's list where the run never said anything."""
    return chat.step(plane_id, cell_id, chat.STEP_FAILED, STALLED, root=root)


def crashed(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    why: nu.StrArg,
    *,
    root: type[Space] = Space,
) -> nu.Nu:
    """Close a run's list where the loop itself died.

    Args:
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that holds the conversation.
        why: the error, as a term or a string. Read once, here: the same
            error also goes into the conversation, and each reader builds its
            own node for it.
        root: the Space shape class.
    """
    return chat.step(
        plane_id, cell_id, chat.STEP_FAILED, nu.Str(CRASHED) + nu.ToStr(why), root=root
    )
