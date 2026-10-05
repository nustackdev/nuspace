"""The two cycles a turn is made of: do the thing, then say what you did.

A turn has exactly two phases and they are not two halves of one loop. The
**work** cycle changes the space, pass after pass, until the model says it is
done. The **answer** cycle draws what the person sees: the response and the
next input form, in one Cell, or no Cell at all when what they should see is
already on a plane, put there in the work cycle (snippets set by their ops).
Either way it says the one line the conversation keeps.

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
without being restarted. :func:`~nuspace.agent.chat.budget_of` and
:func:`~nuspace.agent.chat.patience_of` are where they live.

**And the last thing the answer cycle does is not the answer.** The host
appends the escape hatch under it, every turn, whether or not the model drew
anything: see :func:`hatch`.

**No bracket is held across a pass.** Each read of the session is a snapshot
of its own and each write a short commit. The model's program and the Cell
check load and run outside every bracket, and what they came to is written
after them, so nothing the model wrote ever runs holding the store's lock.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
from nuspace import ops
from nuspace.agent import chat, passes, source
from nuspace.agent import session as memory
from nuspace.agent.shapes import Run
from nuspace.shapes import Reroot


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
    "hosted",
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

#: What stands in the id of the Cell an answer lands in where the panel's stem
#: stands, before the turn number. The number is the panel's, so every Cell a turn leaves carries one number
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
    "`said` holding the one line the conversation keeps and `cell` holding "
    'the whole source of one Cell, or "" when what they should see is '
    "already on a plane. `said` was missing or empty, so nothing was drawn "
    "and nothing was said. Hand it back."
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
        act=_attempted(session=session, panel=panel),
        budget=ceiling(),
        state=state,
    )
    return (
        ops.atomic_state(_opened(session))
        # False before the first pass and not left unset: an unset Bool reads
        # EMPTY and the loop condition would never be a Bool at all.
        >> Run.done.set(nu.Bool(False))
        >> nu.WhileDo(
            ops.snapshot(
                nu.And(
                    nu.And(session.passes < nu.Int(ceiling()), Run.done.not_()),
                    session.repeats < nu.Int(limit()),
                )
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
        act=_handed_back(session=session, panel=panel)
        >> nu.IfDo(
            ops.snapshot(nu.Eq(nu.Str(session.outcome), nu.Str(""))),
            _checked(session=session, panel=panel, ui_plane_id=ui_plane_id),
        ),
        budget=budget,
        state=state,
    )
    return (
        ops.atomic_state(_opened(session) >> session.drawn.set(nu.Bool(False)))
        >> nu.WhileDo(
            ops.snapshot(
                nu.And(
                    nu.And(session.passes < nu.Int(budget), session.drawn.not_()),
                    session.repeats < nu.Int(limit()),
                )
            ),
            body,
        )
        >> nu.IfDo(
            ops.snapshot(nu.Bool(session.drawn)),
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
        A Flow appending one Cell. It draws and never acts, like every other
        drawn Cell: a program that persists runs again whenever somebody opens
        the chat, a week later, with nobody asking.
    """
    return nu.let(
        ops.snapshot(panel.cell()),
        lambda disp: ops.add_cell(
            ui_plane_id,
            chat.OTHER_SOURCE,
            cell_id=_beside(chat.CHAT_OTHER_ID, disp),
            name=_numbered(chat.CHAT_OTHER_NAME, disp),
        ),
    )


def hosted(panel: Panel) -> Reroot:
    """What the host does to a Cell's program on the way in, done to the model's.

    A program the model writes runs inside the talking Cell, so it is loaded
    the way that Cell's own program was: its ``CellState`` lands under the
    talking Cell. It brackets its own store access, as every Cell's program
    does, so the prompt teaches it how.
    """
    return Reroot(panel.plane_id, panel.cell_id)


def _numbered(stem: str, disp: nu.StrArg) -> nu.Nu:
    """``stem`` with this turn's number after it: what a Cell of this turn is called.

    Derived off the panel's id rather than minted, and that is not a shortcut.
    The term a chat runs is built once and runs for the life of the chat, so
    an id minted while it was built would be one id for every turn the chat
    ever takes and the second answer would land on top of the first. The panel
    is already numbered per turn by the submit that made it, so the number is
    there to be read.

    Args:
        stem: what the name starts with.
        disp: the turn's panel Cell, already read.
    """
    return nu.Str(stem) + nu.Str(nu.Str(disp).rpartition(chat.CHAT_DISPLAY_ID)[2])


def _beside(stem: str, disp: nu.StrArg) -> nu.Nu:
    """The id of a Cell of this turn: the panel's, its stem swapped for ``stem``.

    Numbered as :func:`_numbered` is, and scoped as the panel is
    (:func:`~nuspace.agent.chat.scoped`), so it is unique across the space.

    Args:
        stem: what stands where the panel's stem stood.
        disp: the turn's panel Cell, already read.
    """
    return nu.Str(disp).replace(chat.CHAT_DISPLAY_ID, stem)


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
    return asked(panel.cell_id)


def _opened(session: nu.Nu) -> nu.Nu:
    """Zero what a cycle counts, so each of the two starts on its own numbers.

    The repeat counter belongs to a cycle and not to a turn: the work cycle's
    last failure has nothing to do with the answer cycle's first, and carrying
    it across would spend the answer cycle's patience on somebody else's
    mistake.

    No bracket: the caller commits it with whatever else opens its cycle.
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
        ops.snapshot(stuck),
        panel.stuck(cycle, session.repeats, session.failure)
        >> ops.atomic_state(session.stalled.set(said)),
        panel.stalled(cycle) >> ops.atomic_state(session.stalled.set(spent)),
    )


def _attempted(*, session: nu.Nu, panel: Panel) -> nu.Nu:
    """Run the work cycle's program and keep what it came to.

    The draft is read in a snapshot of its own, the program loads and runs
    outside every bracket, and only what it came to is written, in a short
    commit after it. A program that runs for a minute holds no lock for that
    minute, and its own writes are never inside a write bracket of ours.
    """
    return nu.let(
        source.attempted(ops.snapshot(nu.Str(session.draft)), rewrite=hosted(panel)),
        lambda came: ops.atomic_state(session.outcome.set(nu.Str(came))),
    )


def _handed_back(*, session: nu.Nu, panel: Panel) -> nu.Nu:
    """Run the answer cycle's program and keep whatever it handed back.

    The same two catches every pass has, for the same reason: a mistake by the
    model is input rather than a crash, and uncaught it leaves the pass, leaves
    the cycle and kills the chat. What differs is that the yield is kept as a
    value instead of being rendered, because the host is about to build the
    Cell out of it.

    ``outcome`` is written empty on the way through rather than left alone. It
    is what the caller reads to decide whether there is an answer to check, and
    an unwritten one still holds the last pass's complaint.

    The program runs outside every bracket, as in the work cycle, and what it
    handed back is written after it in a commit of its own.
    """

    def missed(why: nu.Nu) -> nu.Nu:
        """No answer this pass, and why. Fresh at each call site."""
        return ops.atomic_state(session.answer.set(nu.Dict.of()) >> session.outcome.set(why))

    handed = nu.Dict(nu.Eval(nu.LoadNu(ops.snapshot(nu.Str(session.draft)), rewrite=hosted(panel))))
    return nu.TryCatch(
        nu.TryCatch(
            nu.let(
                handed,
                lambda answer: ops.atomic_state(
                    session.answer.set(nu.Dict(answer)) >> session.outcome.set(nu.Str(""))
                ),
            ),
            catch=missed(source.failed(reply=session.reply)),
            errors=nu.prog.ConstructionError,
        ),
        catch=missed(nu.Str(MISHANDED) + nu.ToStr(nu.Attr("error")) + nu.Str(MISHANDED_WHY)),
        errors=Exception,
    )


class _Answer(nu.Shape):
    """What one answer pass checks and lands, read once before anything is built."""

    cell = nu.StrRef.slot()
    said = nu.StrRef.slot()
    disp = nu.StrRef.slot()


def _checked(*, session: nu.Nu, panel: Panel, ui_plane_id: nu.StrArg) -> nu.Nu:
    """Build the Cell the model handed back, and append it only if it stands up.

    An answer with no Cell is the line said and nothing drawn: what the
    person should see is already on a plane, put there in the work cycle.
    An answer with no line is not one.

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

    The answer and the panel's id are read once, in snapshots of their own,
    before the check: the check builds the Cell outside every bracket, and
    the append and the line said are each their own op's commit.
    """

    def turn_id() -> nu.Nu:
        """What the Cell this answer lands in is called. Fresh at each site."""
        return _beside(TURN_ID, _Answer.disp)

    def told(why: nu.Nu) -> nu.Nu:
        """The Cell did not build, and why, as the next thing the model reads."""
        return ops.atomic_state(
            session.outcome.set(nu.Str(f"{source.CELL_LABEL}: ") + nu.ToStr(why))
        )

    def spoken() -> nu.Nu:
        """The line said, and the answer marked landed. Fresh at each site."""
        return chat.say(panel.cell_id, chat.ROLE_AGENT, _Answer.said) >> (
            ops.atomic_state(
                session.drawn.set(nu.Bool(True)) >> session.outcome.set(nu.Str(LANDED))
            )
        )

    landed = (
        # An ordinary Cell append rather than ``chat.draw``, for the id: this
        # one is numbered off the panel, which is what ties an answer to its
        # turn. Either way an answer draws and never acts, and that is the
        # whole discipline of one: a Cell's program persists and runs again
        # whenever somebody opens the chat, so an answer that *did* something
        # would do it again, a week later, with nobody asking.
        ops.add_cell(
            ui_plane_id,
            _Answer.cell,
            cell_id=turn_id(),
            name=_numbered(TURN_NAME, _Answer.disp),
        )
        >> spoken()
    )
    checked = nu.TryCatch(
        nu.TryCatch(
            nu.IfDo(
                source.stands(_Answer.cell, plane_id=ui_plane_id, cell_id=turn_id()),
                landed,
            ),
            catch=told(source.diagnostic()),
            errors=nu.prog.ConstructionError,
        ),
        catch=told(nu.Attr("error")),
        errors=Exception,
    )
    return nu.Frame(
        _Answer,
        nu.IfDo(
            nu.Gt(nu.Len(_Answer.said), nu.Int(0)),
            nu.IfDo(nu.Gt(nu.Len(_Answer.cell), nu.Int(0)), checked, spoken()),
            ops.atomic_state(session.outcome.set(nu.Str(INCOMPLETE))),
        ),
        cell=ops.snapshot(memory.drawn_cell_of(panel.cell_id)),
        said=ops.snapshot(memory.said_line_of(panel.cell_id)),
        disp=ops.snapshot(panel.cell()),
    )
