"""The agent a chat runs: it answers by drawing, and the host checks the drawing.

A chat is two Planes. One runs, and the Cell on it is this package. One draws,
and what is on it is whatever this turn and the turns before it put there.
Every turn leaves three Cells on the Plane that draws. Two of them are the
host's: the panel, appended the moment somebody presses send, and the escape
hatch, a folded box appended under the answer so that a person always has a
way to say something. The third is the answer itself, which is the response
and the next input form in one. The reply box is not chrome any more, it is a
Cell a model wrote, so it can just as well be three buttons, a form, a slider,
or a diff with approve and reject on it.

What stays uniform is the **record**. Whatever the person does through whatever
was drawn lands in the conversation as an ordinary ``{role, text}`` message,
and that list is what wakes the agent for the next turn. Cells are
presentation; the conversation is the truth.

That is natural here and awkward anywhere else, because a Cell's program is
Nu: what the model generates is a live program bound to the store rather than
a dead render of a payload. It also persists as an ordinary Cell, so a person
can open what the agent made and edit it.

The structure, and every word of it is load bearing::

    chat        the conversation. one input runs a turn
     turn       one input, looped until done
      cycle     a phase of the turn. exactly two: work, then answer
       pass     one model call plus the program it wrote

The modules::

    chat            what was said, the trace, and the submit that starts it
    conversation    the chat loop and the turn: heard, work, answer
    cycles          the two cycles, and the check before an answer lands
    passes          one pass, composed, with the host's rows between the links
    trace           those rows: the fixed machine, and where it is written
    session         a turn's working memory, in the store, under the chat
    shapes          the slots it runs on, and the one slot the model writes
    source          fenced extraction, one attempt, and the Cell check
    panel           display(): the trace of one turn, hardcoded, drawn live
    cc              Claude Code. one conversation, kept across restarts
    llm             a served model over the OpenAI wire. one call per pass
    prompt          what the model reads, as markdown on disk

**The pass is composed here rather than taken from nuagent, and that is the
whole point of the move.** nuagent's ``turn`` is one opaque composed Flow, so
there is nowhere to stand between the model call going out and the program
coming back, and a chat wearing it showed a person a blank panel for a minute
and then everything at once. Composing it here buys six places to stand.
nuagent stays where it is and keeps working; we stopped importing it.

**Two entry points onto one core.** :func:`converse` is a chat: two cycles,
a conversation, a drawn answer. :func:`perform` is a job agent: the work cycle
with a fixed task and no drawing. Splitting them later is cheap and nothing
about the core would have to move.

**Three names are not imported until somebody asks for one**, and that is not
tidiness, it is what the two kinds of Cell in here cost each other. The Cell
that draws a chat's panel wants :func:`display` and no model; the Cell that
talks wants an endpoint and draws nothing. Imported eagerly, each pays for the
other: ``nustd.cc`` pulls the Claude Code SDK, which is most of a second, and
``nuspace.agent.panel`` pulls ``nustd.ui``, which is a third of one. A panel
Cell is launched in a fresh worker every time somebody navigates to a chat, so
that is most of a second of Claude Code SDK on every navigation for a Cell
that will never speak. :data:`DEFERRED` is the table and the module
``__getattr__`` below is the whole of the mechanism.

**This package is where the behaviour lives, not the Plane.** A chat's
talking Cell holds a few lines that call :func:`converse` with an endpoint,
so installing a newer nuspace upgrades every chat already in the store. A
Plane's cells are seeds and a seed has no migration; for a prompt that gets
tuned daily, seeding is the wrong shape. Which endpoint a chat talks to is
the one thing the Plane decides.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from nuspace.agent import chat, conversation, cycles, passes, prompt, session, source, trace
from nuspace.agent.shapes import Run, Session, Turn


if TYPE_CHECKING:
    from collections.abc import Callable

    import nu
    from nuspace.agent.panel import display


__all__ = [
    "DEFERRED",
    "Run",
    "Session",
    "Turn",
    "chat",
    "claude_code",
    "conversation",
    "converse",
    "cycles",
    "display",
    "passes",
    "perform",
    "prompt",
    "served_model",
    "session",
    "source",
    "trace",
]


#: The names that cost an import nobody else here needs, by the module each
#: lives in. Read by :func:`__getattr__`, so ``nuspace.agent.display`` still
#: resolves and the import it costs is paid by whoever asked for it.
DEFERRED = {"claude_code": "cc", "display": "panel", "served_model": "llm"}


def __getattr__(name: str) -> object:
    """Resolve one of :data:`DEFERRED` by importing the module it lives in.

    Python calls this only for names the module does not already have, so it
    costs nothing on any other attribute, and the result is cached by the
    ordinary import machinery rather than by anything here.
    """
    if name in DEFERRED:
        return getattr(import_module(f"{__name__}.{DEFERRED[name]}"), name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def converse(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    *,
    ui_plane_id: nu.StrArg,
    talk: Callable[..., nu.Nu],
) -> nu.Nu:
    """The whole term a chat's talking Cell runs.

    Answer whatever is outstanding, then wait for more, forever, with the
    endpoint held open around all of it.

    Args:
        plane_id: the Plane the chat runs on. The Cell's own ``plane``.
        cell_id: the Cell on it that talks and holds the conversation. The
            Cell's own ``cell``.
        ui_plane_id: the Plane the agent draws its answers onto. The other
            half of the pair a chat is, and the one the person is looking at.
        talk: the endpoint, ``endpoint(loop, *, system, plane_id,
            cell_id)``, e.g. :func:`~nuspace.agent.cc.claude_code` or
            :func:`~nuspace.agent.llm.served_model`. Which model a chat talks
            to is the Plane's choice, so there is no default here.

    Returns:
        A Flow that never ends on its own.

    Notes:
        - Every store access inside is a short bracket of its own, and none
          is held across a model call, a wait or the model's program. The
          model's programs are rerooted under the talking Cell and bracket
          themselves, as every Cell's program does.
        - The endpoint goes up once, outside the wait, so a session lasts as
          long as the Cell runs rather than as long as a turn. It is handed
          the talking Cell, so an endpoint that holds a conversation can keep
          its id there and a restarted Cell carries on with it.
    """

    def loop(ask: Callable[..., nu.Nu]) -> nu.Nu:
        return conversation.answering(plane_id, cell_id, ui_plane_id=ui_plane_id, ask=ask)

    return talk(loop, system=prompt.system_prompt(), plane_id=plane_id, cell_id=cell_id)


def perform(
    plane_id: nu.StrArg,
    cell_id: nu.StrArg,
    task: str,
    *,
    talk: Callable[..., nu.Nu],
) -> nu.Nu:
    """One job agent: the work cycle, a fixed task, and no drawing.

    The narrow half of the same core. Nobody is talking to a job agent, so
    there is nothing to hear and nothing to answer, and what is left is the
    cycle that changes the space. It narrates into its own Cell's state, so
    :func:`display` over that Cell shows a job doing its work exactly the way
    it shows a chat doing a turn.

    Args:
        plane_id: the Plane the job runs on. The Cell's own ``plane``.
        cell_id: the Cell doing the work. The Cell's own ``cell``.
        task: what to do, in prose. It goes in the prompt and again as the
            first message, because a prompt is what a model is told once and
            a message is what it is looking at.
        talk: the endpoint, as for :func:`converse`. It is handed the job's
            Cell the same way, so a job that is run again picks up the
            conversation it had.

    Returns:
        A Flow that runs the work cycle once and ends.
    """

    def once(ask: Callable[..., nu.Nu]) -> nu.Nu:
        return conversation.performing(plane_id, cell_id, task, ask=ask)

    return talk(
        once,
        system=prompt.system_prompt(task=task, drawing=False),
        plane_id=plane_id,
        cell_id=cell_id,
    )
