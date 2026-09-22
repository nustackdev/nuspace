"""The two cycles a turn is made of: do the thing, then say what you did.

A turn has exactly two phases and they are not two halves of one loop. The
**work** cycle changes the space, pass after pass, until the model says it is
done. The **answer** cycle draws what the person sees: the response and the
next input form, in one Cell.

**The answer cycle is a loop of its own, and that is the point of it.** A
chat's answer is itself the source of a Cell, and a Cell is only ever built
when somebody opens the chat. A model that wrote a broken one would find out
never; the person would find out by looking at a row that says it failed. So
the host builds it first, validates it, and only appends what stood up.
Anything that did not comes back as the next thing the model reads, exactly
the way a module that would not construct does, and the model fixes it.

**Which means the model does not write in the answer cycle.** Its program
hands back a value: the Cell's source, and the line the conversation keeps.
The host does the appending, because the host is what checked it. That is the
one place a program here is a pure read, and it is what makes
"before appending" possible at all.

**Both exits are the model's.** The work cycle ends when the model sets
``Run.done`` in the program it wrote. The answer cycle ends when the model
hands back an answer that stands up. Neither is a host predicate over the
world: a state predicate tests what a program did, not whether the job is
done, and it is gameable, duplicated against the prose task, and unwritable
for anything judgement-shaped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
from nuspace import ops
from nuspace.agent import passes, source
from nuspace.agent import session as memory
from nuspace.agent.shapes import Run
from nuspace.ops import chat, groups
from nuspace.shapes import RESTART_NO


if TYPE_CHECKING:
    from collections.abc import Callable

    from nuspace.agent.trace import Panel


__all__ = [
    "ANSWER_PASSES",
    "INCOMPLETE",
    "LANDED",
    "TURN_ID",
    "TURN_NAME",
    "WORK_PASSES",
    "answer",
    "work",
]


#: Passes one work cycle gets. Small on purpose: a question that has not been
#: worked out in this many is usually one that needed splitting, and a model
#: editing a live Space is cheaper to re-ask than to let wander.
WORK_PASSES = 8

#: Passes one answer cycle gets. Smaller, because there is one thing to do in
#: it and every pass after the first is the model repairing a Cell it already
#: wrote. Four is three repairs, which is more than a model that is going to
#: get there ever needs.
ANSWER_PASSES = 4

#: What the Cell an answer lands in is called, before the turn number. The
#: number is the panel's, so a turn's two Cells carry one number between them
#: and a reader scrolling back can see which answer goes with which trace.
TURN_ID = "c_turn_"

#: And what a person sees it called in the sidebar. Not ``turn``, because
#: the panel beside it already carries that word and a turn's two Cells
#: reading the same in a list is two rows nobody can tell apart.
TURN_NAME = "answer "

#: The outcome of a pass whose answer stood up and landed. Short, because it
#: is a panel row and because there is no next pass to read it.
LANDED = "the answer is on the screen and in the record"

#: What a model is told when it handed back something that is not an answer.
INCOMPLETE = (
    f"{source.ANSWER_LABEL}: an answer is a dict with two keys in it, "
    "`cell` holding the whole source of one Cell and `said` holding the one "
    "line the conversation keeps. One of them was missing or empty, so "
    "nothing was drawn and nothing was said. Hand back both."
)

#: What a model is told when its program ran and what came back was not an
#: answer at all. The error rides after it, on the first line, because the
#: shape of the failure says which mistake it was and the panel shows one
#: line. The commonest one by far is a program that wrote: a write yields
#: nothing, so the host is handed ``None``, which is why the explanation
#: names that case outright.
MISHANDED = f"{source.ANSWER_LABEL}: your program handed back something else: "

#: And the rest of it, on its own line, for the model rather than the panel.
MISHANDED_WHY = (
    "\nAn answer is nu.Dict.of(cell=..., said=...) and nothing else. If you "
    "wrote to the space in that program, that is the reason: a program that "
    "writes is a Flow and a Flow yields nothing. The answer cycle hands back "
    "a value; it never writes. Work is over by the time you are in it."
)


def work(
    *,
    session: nu.Nu,
    panel: Panel,
    ask: Callable[..., nu.Nu],
    state: nu.Nu | None = None,
    budget: int = WORK_PASSES,
) -> nu.Nu:
    """Do what the person asked for, pass after pass, until the model is done.

    The cycle nuagent already is, with the rows written in. The model's
    program acts on the space, the outcome of running it becomes the next
    thing the model reads, and the exit is the slot the model writes.

    Args:
        session: the turn's slots, as the ref they hang off.
        panel: where this turn's rows go.
        ask: what reaches the model.
        state: the world after each program ran, shown to the model.
        budget: how many passes it gets.

    Returns:
        A Flow that ends when the model sets ``Run.done`` or the budget runs
        out, and says which of the two happened in its last row.
    """
    body = passes.one(
        session=session,
        panel=panel,
        ask=ask,
        cycle=chat.CYCLE_WORK,
        act=session.outcome.set(nu.Str(source.attempted(session.draft))),
        budget=budget,
        state=state,
    )
    return (
        session.passes.set(nu.Int(0))
        # False before the first pass and not left unset: an unset Bool reads
        # EMPTY and the loop condition would never be a Bool at all.
        >> Run.done.set(nu.Bool(False))
        >> nu.WhileDo(nu.And(session.passes < nu.Int(budget), Run.done.not_()), body)
        >> nu.IfDo(
            Run.done,
            panel.finished(chat.CYCLE_WORK),
            panel.stalled(chat.CYCLE_WORK),
        )
    )


def answer(
    *,
    session: nu.Nu,
    panel: Panel,
    ask: Callable[..., nu.Nu],
    ui_plane_id: nu.StrArg,
    state: nu.Nu | None = None,
    budget: int = ANSWER_PASSES,
) -> nu.Nu:
    """Draw what the person sees, and do not append anything that will not build.

    Args:
        session: the turn's slots, as the ref they hang off.
        panel: where this turn's rows go.
        ask: what reaches the model.
        ui_plane_id: the Plane the answer is drawn onto.
        state: the world after each program ran, shown to the model.
        budget: how many passes it gets.

    Returns:
        A Flow that ends when an answer has landed or the budget runs out. It
        says nothing into the conversation on its own: the record is part of
        the answer, and a cycle that never landed one is the caller's to close.
    """
    body = passes.one(
        session=session,
        panel=panel,
        ask=ask,
        cycle=chat.CYCLE_ANSWER,
        act=_handed_back(session=session)
        >> nu.IfDo(
            nu.Eq(nu.Str(session.outcome), nu.Str("")),
            _checked(session=session, panel=panel, ui_plane_id=ui_plane_id),
        ),
        budget=budget,
        state=state,
    )
    return (
        session.passes.set(nu.Int(0))
        >> session.drawn.set(nu.Bool(False))
        >> nu.WhileDo(nu.And(session.passes < nu.Int(budget), session.drawn.not_()), body)
        >> nu.IfDo(
            session.drawn,
            panel.finished(chat.CYCLE_ANSWER),
            panel.stalled(chat.CYCLE_ANSWER),
        )
    )


def _handed_back(*, session: nu.Nu) -> nu.Nu:
    """Run the answer cycle's program and keep whatever it handed back.

    The same two catches every pass has, for the same reason: a mistake by the
    model is input rather than a crash, and uncaught it leaves the pass, leaves
    the cycle and kills the chat. What differs is that the yield is kept as a
    value instead of being rendered, because the host is about to build the
    Cell out of it.

    ``outcome`` is written empty on the way through rather than left alone. It
    is what the caller reads to decide whether there is an answer to check, and
    an unwritten one still holds the last pass's complaint.
    """
    return nu.TryCatch(
        nu.TryCatch(
            session.answer.set(nu.Dict(nu.Eval(nu.LoadNu(session.draft))))
            >> session.outcome.set(nu.Str("")),
            catch=session.answer.set(nu.Dict.of())
            >> session.outcome.set(source.failed(reply=session.reply)),
            errors=nu.prog.ConstructionError,
        ),
        catch=session.answer.set(nu.Dict.of())
        >> session.outcome.set(
            nu.Str(MISHANDED) + nu.ToStr(nu.AttrRef("error")) + nu.Str(MISHANDED_WHY)
        ),
        errors=Exception,
    )


def _checked(*, session: nu.Nu, panel: Panel, ui_plane_id: nu.StrArg) -> nu.Nu:
    """Build the Cell the model handed back, and append it only if it stands up.

    The whole of what the answer cycle is for. :func:`nuspace.agent.source.stands`
    goes in the ``cond`` slot because that is the one place a Flow takes a
    Query, and because what it does there is exactly what a condition is: the
    body runs if the Cell builds. It never answers False, it raises, so the two
    catches around it are what turn a broken Cell into the next thing the model
    reads.

    The label is :data:`~nuspace.agent.source.CELL_LABEL` and not the one a
    module that would not construct gets. There are two pieces of source in an
    answer pass, and a model told only "CONSTRUCTION FAILED" would go looking
    at the wrong one.
    """

    def cell_source() -> nu.Nu:
        """The Cell the model handed back. Fresh at each call site."""
        return memory.drawn_cell_of(panel.plane_id, panel.cell_id, root=panel.root)

    def said() -> nu.Nu:
        """The line the conversation keeps. Fresh at each call site."""
        return memory.said_line_of(panel.plane_id, panel.cell_id, root=panel.root)

    def turn_id() -> nu.Nu:
        """What the Cell this answer lands in is called.

        Derived off the panel's id rather than minted, and that is not a
        shortcut. The term a chat runs is built once and runs for the life of
        the chat, so an id minted while it was built would be one id for every
        turn the chat ever takes and the second answer would land on top of the
        first. The panel is already numbered per turn by the submit that made
        it, so the number is there to be read.
        """
        return nu.Str(TURN_ID) + nu.Str(panel.cell()).removeprefix(groups.CHAT_DISPLAY_ID)

    def turn_name() -> nu.Nu:
        """And what a person sees it called. Fresh at each call site."""
        return nu.Str(TURN_NAME) + nu.Str(panel.cell()).removeprefix(groups.CHAT_DISPLAY_ID)

    landed = (
        # An ordinary Cell append rather than ``ops.chat.draw``, for the id:
        # ``draw`` mints one while the tree is built, which is right for a
        # model whose program is loaded fresh every pass and wrong for a host
        # term built once. ``restart`` is ``no`` either way, and that is the
        # whole discipline of a drawn answer: a Cell's program persists and
        # runs again on every reload, so an answer that *did* something would
        # do it again, a week later, with nobody asking.
        ops.add_cell(
            ui_plane_id,
            cell_source(),
            cell_id=turn_id(),
            name=turn_name(),
            restart=RESTART_NO,
            root=panel.root,
        )
        >> chat.say(panel.plane_id, panel.cell_id, chat.ROLE_AGENT, said(), root=panel.root)
        >> session.drawn.set(nu.Bool(True))
        >> session.outcome.set(nu.Str(LANDED))
    )
    checked = nu.TryCatch(
        nu.TryCatch(
            nu.IfDo(
                source.stands(cell_source(), plane_id=ui_plane_id, cell_id=turn_id()),
                landed,
            ),
            catch=session.outcome.set(
                nu.Str(f"{source.CELL_LABEL}: ") + nu.ToStr(source.diagnostic())
            ),
            errors=nu.prog.ConstructionError,
        ),
        catch=session.outcome.set(nu.Str(f"{source.CELL_LABEL}: ") + nu.ToStr(nu.AttrRef("error"))),
        errors=Exception,
    )
    return nu.IfDo(
        nu.And(
            nu.Gt(nu.Len(cell_source()), nu.Int(0)),
            nu.Gt(nu.Len(said()), nu.Int(0)),
        ),
        checked,
        session.outcome.set(nu.Str(INCOMPLETE)),
    )
