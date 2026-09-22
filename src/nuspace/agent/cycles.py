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

**What stops a cycle that is not going to end is not a budget.** A tally big
enough to let real work finish is a tally that never fires, and one small
enough to fire is one that cuts a chat off mid task and hands the person
nothing. The thing worth stopping is narrower than "this is taking a while":
it is a model repeating one failure, which it will repeat forever, on an
endpoint that costs money per pass. So the guard is the repeat and not the
count, the far ceiling above it is a backstop rather than a policy, and both
are read out of the chat so a run that is grinding can be given more room
without being restarted. :func:`~nuspace.ops.chat.budget_of` and
:func:`~nuspace.ops.chat.patience_of` are where they live.

**And the last thing the answer cycle does is not the answer.** The host
appends the escape hatch under it, every turn, whether or not the model drew
anything: see :func:`hatch`.
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
    "SPENT",
    "STUCK_HEAD",
    "STUCK_LINE",
    "STUCK_TIMES",
    "TURN_ID",
    "TURN_NAME",
    "answer",
    "hatch",
    "work",
]


#: Passes one answer cycle gets, and the one budget here that is a number in
#: python rather than a fact about a chat. There is one thing to do in this
#: cycle and every pass after the first is the model repairing a Cell it
#: already wrote, so more tries is not what fixes a Cell that will not build.
#: Four is three repairs, which is more than a model that is going to get
#: there ever needs.
ANSWER_PASSES = 4

#: What the person is told when a cycle gave up, before the cycle's name.
STUCK_HEAD = "The "

#: And after it, before how many times in a row the same thing went wrong.
STUCK_TIMES = " cycle gave up: it hit the same failure "

#: And after that, before the failure itself. It says stuck rather than slow,
#: because those are different things and the person can only act on one of
#: them: a run that was going to get there was not stopped by this.
STUCK_LINE = " times in a row, so trying again was not going to help. "

#: What the person is told when a cycle used every pass it had. The ceiling is
#: far away and nothing is expected to reach it, so reaching it is worth
#: saying in its own words rather than as a kind of being stuck.
SPENT = " cycle ran out of passes before it finished. "

#: What the Cell an answer lands in is called, before the turn number. The
#: number is the panel's, so every Cell a turn leaves carries one number
#: between them and a reader scrolling back can see which answer goes with
#: which trace.
TURN_ID = "c_turn_"

#: And what a person sees it called in the sidebar. Not ``turn``, because the
#: panel beside it already carries that word and two rows in a list reading
#: the same is two rows nobody can tell apart.
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
    budget: nu.IntArg | None = None,
    patience: nu.IntArg | None = None,
) -> nu.Nu:
    """Do what the person asked for, pass after pass, until the model is done.

    The cycle nuagent already is, with the rows written in. The model's
    program acts on the space, the outcome of running it becomes the next
    thing the model reads, and the exit is the slot the model writes.

    Long work is allowed to be long. The model knows when the work is done and
    the host does not, so the only thing the host stops is a model that has
    stopped getting anywhere, which is :func:`~nuspace.agent.passes.one`
    counting one failure repeating. The ceiling above that exists so a spin
    the repeat check cannot see still ends.

    Args:
        session: the turn's slots, as the ref they hang off.
        panel: where this turn's rows go.
        ask: what reaches the model.
        state: the world after each program ran, shown to the model.
        budget: the pass ceiling. Read off the chat when absent, which is what
            makes it raiseable mid run.
        patience: how many identical failures in a row to allow. Read off the
            chat when absent, for the same reason.

    Returns:
        A Flow that ends when the model sets ``Run.done``, when it has failed
        the same way ``patience`` times, or when it has used the ceiling. It
        says which of the three happened in its last row.
    """

    def ceiling() -> nu.Nu:
        """How many passes this chat allows. Fresh at each call site."""
        return _allowed(panel, budget, chat.budget_of)

    def limit() -> nu.Nu:
        """How many identical failures it allows. Fresh at each call site."""
        return _allowed(panel, patience, chat.patience_of)

    body = passes.one(
        session=session,
        panel=panel,
        ask=ask,
        cycle=chat.CYCLE_WORK,
        act=session.outcome.set(nu.Str(source.attempted(session.draft))),
        budget=ceiling(),
        state=state,
    )
    return (
        _opened(session)
        # False before the first pass and not left unset: an unset Bool reads
        # EMPTY and the loop condition would never be a Bool at all.
        >> Run.done.set(nu.Bool(False))
        >> nu.WhileDo(
            nu.And(
                nu.And(session.passes < nu.Int(ceiling()), Run.done.not_()),
                session.repeats < nu.Int(limit()),
            ),
            body,
        )
        >> nu.IfDo(
            Run.done,
            panel.finished(chat.CYCLE_WORK),
            _gave_up(session=session, panel=panel, cycle=chat.CYCLE_WORK, patience=limit()),
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
    patience: nu.IntArg | None = None,
) -> nu.Nu:
    """Draw what the person sees, and do not append anything that will not build.

    The one cycle that keeps a real pass budget, because here a pass that did
    not work is a Cell that did not build and the fix for that is a different
    Cell rather than another try at the same one.

    Args:
        session: the turn's slots, as the ref they hang off.
        panel: where this turn's rows go.
        ask: what reaches the model.
        ui_plane_id: the Plane the answer is drawn onto.
        state: the world after each program ran, shown to the model.
        budget: how many passes it gets.
        patience: how many identical failures in a row to allow. Read off the
            chat when absent.

    Returns:
        A Flow that ends when an answer has landed, when the same failure has
        come back ``patience`` times, or when the budget runs out, and which
        appends the escape hatch either way. It says nothing into the
        conversation on its own: the record is part of the answer, and a cycle
        that never landed one is the caller's to close.
    """

    def limit() -> nu.Nu:
        """How many identical failures it allows. Fresh at each call site."""
        return _allowed(panel, patience, chat.patience_of)

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
        _opened(session)
        >> session.drawn.set(nu.Bool(False))
        >> nu.WhileDo(
            nu.And(
                nu.And(session.passes < nu.Int(budget), session.drawn.not_()),
                session.repeats < nu.Int(limit()),
            ),
            body,
        )
        >> nu.IfDo(
            session.drawn,
            panel.finished(chat.CYCLE_ANSWER),
            _gave_up(session=session, panel=panel, cycle=chat.CYCLE_ANSWER, patience=limit()),
        )
        >> hatch(panel=panel, ui_plane_id=ui_plane_id)
    )


def hatch(*, panel: Panel, ui_plane_id: nu.StrArg) -> nu.Nu:
    """Append the escape hatch under whatever this turn drew.

    The host's, every turn, and the model is never asked. The reason is a
    failure that actually happens: a turn draws three buttons, forgets the
    fourth, and the person has no way to say anything else at all. Uniform and
    always there is the same rule that makes the panel host owned, so this is
    owned the same way, appended after the answer, and unsuppressable.

    Outside the loop rather than beside the append inside it, so a turn that
    never landed an answer still gets one. That is the turn that needs it
    most: the person is looking at a panel that says it gave up.

    Args:
        panel: this turn's panel, which is where the turn number comes from
            and which carries the chat the hatch submits to.
        ui_plane_id: the Plane the chat draws onto.

    Returns:
        A Flow appending one Cell. ``restart`` is ``no`` like every other
        drawn Cell: a program that persists would otherwise run again, a week
        later, with nobody asking.
    """
    return ops.add_cell(
        ui_plane_id,
        groups.CHAT_OTHER.program(panel.plane_id, root=panel.root),
        cell_id=_numbered(groups.CHAT_OTHER_ID, panel),
        name=_numbered(groups.CHAT_OTHER_NAME, panel),
        restart=RESTART_NO,
        root=panel.root,
    )


def _numbered(stem: str, panel: Panel) -> nu.Nu:
    """``stem`` with this turn's number after it: an id, or a name.

    Derived off the panel's id rather than minted, and that is not a shortcut.
    The term a chat runs is built once and runs for the life of the chat, so
    an id minted while it was built would be one id for every turn the chat
    ever takes and the second answer would land on top of the first. The panel
    is already numbered per turn by the submit that made it, so the number is
    there to be read.

    Fresh at each call site, because ``panel.cell()`` is a read.
    """
    return nu.Str(stem) + nu.Str(panel.cell()).removeprefix(groups.CHAT_DISPLAY_ID)


def _allowed(panel: Panel, given: nu.IntArg | None, asked: Callable[..., nu.Nu]) -> nu.Nu:
    """A limit: the one handed in, or the one the chat holds.

    Read while the tree runs rather than settled when it is built, which is
    the whole point of keeping it in the store: a chat that is grinding can be
    given more room from anywhere that can write, and the loop it is already
    inside picks the new number up on its next pass.

    Fresh at each call site, like every other address here.
    """
    if given is not None:
        return nu.Int(given)
    return asked(panel.plane_id, panel.cell_id, root=panel.root)


def _opened(session: nu.Nu) -> nu.Nu:
    """Zero what a cycle counts, so each of the two starts on its own numbers.

    The repeat counter belongs to a cycle and not to a turn: the work cycle's
    last failure has nothing to do with the answer cycle's first, and carrying
    it across would spend the answer cycle's patience on somebody else's
    mistake.
    """
    return (
        session.passes.set(nu.Int(0))
        >> session.repeats.set(nu.Int(0))
        >> session.failure.set(nu.Str(""))
    )


def _gave_up(*, session: nu.Nu, panel: Panel, cycle: str, patience: nu.Nu) -> nu.Nu:
    """A cycle ended without its exit: say which way, in the panel and to the person.

    Two readers and one fact. The panel gets a row, because somebody watching
    a turn wants to see where it stopped. ``stalled`` gets the sentence, which
    is what the host says into the conversation if the turn never answered:
    "that run ended without an answer" tells a person nothing they can act on,
    and "it hit the same failure three times" tells them to ask differently.
    """
    stuck = nu.Ge(nu.Int(session.repeats), nu.Int(patience))
    said = (
        nu.Str(STUCK_HEAD)
        + nu.Str(cycle)
        + nu.Str(STUCK_TIMES)
        + nu.ToStr(nu.Int(session.repeats))
        + nu.Str(STUCK_LINE)
        + nu.Str(session.failure)
    )
    spent = nu.Str(STUCK_HEAD) + nu.Str(cycle) + nu.Str(SPENT)
    return nu.IfDo(
        stuck,
        panel.stuck(cycle, session.repeats, session.failure) >> session.stalled.set(said),
        panel.stalled(cycle) >> session.stalled.set(spent),
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
        """What the Cell this answer lands in is called. Fresh at each site."""
        return _numbered(TURN_ID, panel)

    def turn_name() -> nu.Nu:
        """And what a person sees it called. Fresh at each call site."""
        return _numbered(TURN_NAME, panel)

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
