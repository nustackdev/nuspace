"""The fixed machine, written down between the links of a pass.

A turn takes as long as it takes, and until it ends the person has nothing to
look at. So the host narrates it: one row at every point in a pass where
something observable happened, into the trace of the turn's own panel, where
:func:`nuspace.agent.display.display` draws it live.

**This is the whole reason the pass is composed here rather than taken from
somebody else.** nuagent's ``turn`` is one opaque composed Flow, so there is
nowhere to stand between "the model call goes out" and "the program ran", and
a chat wearing it showed a burst of progress at the end and nothing before it.
Composing the pass ourselves buys six places to stand, and the rows below are
what stands in them.

**Two writers, and the split is about who knows.** The host owns the shape of
a turn and writes it here: heard, thinking, writing, running, failed, done.
The model owns what the work *was*, because what a program was for is known
only to whoever wrote it, and "renamed the Notes plane" is a sentence no host
can compose out of a term it did not author. That half is
:func:`nuspace.ops.chat.note`, and it is taught in the prompt rather than
written here.

The texts are constants rather than inline literals for the ordinary reason:
they are read by a person in a panel, they get reworded, and a reworded line
is a line somebody has to find.
"""

from __future__ import annotations

from dataclasses import dataclass

import nu
from nuspace.agent import session as memory
from nuspace.agent.source import complaint
from nuspace.ops import chat
from nuspace.shapes import Space


__all__ = [
    "CRASHED",
    "ELLIPSIS",
    "FINISHED",
    "LINE",
    "OF",
    "OUT_OF_PASSES",
    "PASS",
    "SAME",
    "STUCK",
    "TIMES",
    "Panel",
    "asked",
    "clipped",
    "head",
    "session_slots",
]


#: What a pass's own row starts with, before the count.
PASS = "pass "  # noqa: S105 -- a panel row, not a secret

#: What separates the count from what it is counting against. A count on its
#: own says a cycle is moving; a count against a ceiling says how much room is
#: left, which is the question somebody watching a slow chat is asking.
OF = " of "

#: The last row of a cycle that ended because the model said so. Which cycle
#: goes after it, because a reader scrolling a finished turn sees two of these
#: and they mean different things.
FINISHED = "finished: "

#: A cycle that used its passes without the model ever saying it was done.
OUT_OF_PASSES = "out of passes: "

#: A cycle that stopped because it was going in circles rather than because it
#: ran long. Which cycle goes after it.
STUCK = "stuck: "

#: And then how many times the same thing went wrong.
SAME = " failed the same way "

#: And then the thing itself, which is the one row here worth reading twice.
TIMES = " times: "

#: The loop itself dying, with the error after it. The model's own mistakes
#: never reach this: a module that will not construct is fed back to it and
#: the turn carries on.
CRASHED = "the turn crashed: "

#: How much of one line the panel keeps. A row is a line in a table somebody
#: is watching, and a diagnostic runs to a screenful, so the choice is between
#: cutting it here and a panel that is one traceback tall. What was cut is in
#: the conversation the model is having, which is where anybody debugging a
#: pass is reading anyway.
LINE = 200

#: What says a line was cut. Three dots rather than the character, because
#: this goes in a table cell beside monospaced ids.
ELLIPSIS = "..."


def clipped(line: nu.Nu) -> nu.Nu:
    """``line`` cut to :data:`LINE`, with :data:`ELLIPSIS` where it was cut."""
    return nu.Str(
        nu.If(
            nu.Gt(nu.Len(line), nu.Int(LINE)),
            nu.Str(line[0:LINE]) + nu.Str(ELLIPSIS),
            nu.Str(line),
        )
    )


def head(text: nu.Nu) -> nu.Nu:
    """The first line of ``text``, empty where there is none.

    Floored, because an empty string splits to an empty list and reading index
    zero of one yields INVALID, which writes nothing and raises nothing. A
    cycle that has not had a pass yet is exactly that case.
    """
    lines = nu.Str(text).splitlines()
    return nu.Str(
        nu.If(
            nu.Gt(nu.Len(lines), nu.Int(0)),
            nu.Str(nu.List(lines)[nu.Int(0)]),
            nu.Str(""),
        )
    )


@dataclass(frozen=True)
class Panel:
    """Where one turn's trace goes, and every row the host writes into it.

    Three ids and a root, because a row is addressed by the Plane that draws
    the chat and the display Cell on it, and which display Cell that is comes
    off the chat. Carried together rather than threaded through a dozen
    signatures: every one of the rows below wants all four and nothing wants a
    subset.

    Attributes:
        ui_plane_id: the Plane the chat draws onto, which is the Plane every
            panel is on.
        plane_id: the Plane that runs the chat.
        cell_id: the Cell on it that talks.
        root: the Space shape class.
        disp_cell_id: which Cell to write into, for a caller that already
            knows. A chat's panel is a different Cell every turn and has to be
            asked for; a job agent's is its own Cell and is known outright.
    """

    ui_plane_id: nu.StrArg
    plane_id: nu.StrArg
    cell_id: nu.StrArg
    root: type[Space] = Space
    disp_cell_id: nu.StrArg | None = None

    def cell(self) -> nu.Nu:
        """Which display Cell this turn is writing into. Fresh at each site.

        Read while the tree runs rather than settled when it is built. A
        chat's panel is a different Cell every turn and the term a chat runs
        is built once, so for a chat this is a question and not a value.
        """
        if self.disp_cell_id is not None:
            return nu.Str(self.disp_cell_id)
        return chat.latest_display(self.plane_id, self.cell_id, root=self.root)

    def state(self, cycle: nu.StrArg, kind: nu.StrArg, text: nu.StrArg) -> nu.Nu:
        """One host row. The fixed machine, and the only thing that writes it."""
        return chat.state(self.ui_plane_id, self.cell(), cycle, kind, text, root=self.root)

    def heard(self, what: nu.StrArg) -> nu.Nu:
        """What started this turn, before anything runs.

        The first row of every turn and the one that has to land fastest: it is
        what turns a blank panel into a panel, and it needs no model call to
        write, so it is up before the endpoint has been asked anything.
        """
        return self.state(chat.CYCLE_WORK, chat.KIND_HEARD, clipped(nu.Str(what)))

    def thinking(self, cycle: nu.StrArg) -> nu.Nu:
        """The prose of the pass before this one, as the next call goes out.

        The previous pass's, and that is not an off-by-one. A model call is one
        atom: there is no moment inside it to write anything, so the row that
        goes up while a person waits has to be written before it, and the
        newest prose there is at that moment is what came back last time.

        Nothing is written where the last reply was all code, or where there
        has not been one. A model that answers with a bare program has said
        nothing, and a blank row in a panel reads as something having gone
        wrong.
        """
        return nu.IfDo(
            nu.Gt(nu.Len(self._said()), nu.Int(0)),
            self.state(cycle, chat.KIND_THINKING, clipped(self._said())),
        )

    def writing(self, cycle: nu.StrArg, *, budget: nu.IntArg) -> nu.Nu:
        """Which pass this is, against the cycle's ceiling, once source is out.

        The backstop under everything else in the panel. A model that narrates
        nothing and draws nothing still moves this, so a turn is never a list
        that stops growing, and a count somebody can read is what tells the
        difference between a cycle working and a cycle circling.

        The ceiling is a term and not a number, because for the work cycle it
        is a fact about the chat that anything can raise while the chat is
        running. A row is what says the new one took.
        """
        counted = (
            nu.Str(PASS)
            + nu.ToStr(memory.passes_of(self.plane_id, self.cell_id, root=self.root))
            + nu.Str(OF)
            + nu.ToStr(nu.Int(budget))
        )
        return self.state(cycle, chat.KIND_WRITING, counted)

    def ran(self, cycle: nu.StrArg) -> nu.Nu:
        """What the program came to: its yield, or the first line of why not.

        One row either way and two kinds, because a reader draws a row by its
        kind and those two want to look different. The split is read off the
        text, since a yield and a diagnostic land in the same slot: that is
        right for the model, which reads either the same way, and leaves the
        host to tell them apart by the label each carries.
        """

        def wrong() -> nu.Nu:
            """Whether the outcome is a diagnostic. Fresh at each call site."""
            return complaint(head(self._outcome()))

        return nu.IfDo(
            wrong(),
            self.state(cycle, chat.KIND_FAILED, clipped(head(self._outcome()))),
            self.state(cycle, chat.KIND_RUNNING, clipped(self._outcome())),
        )

    def finished(self, cycle: nu.StrArg) -> nu.Nu:
        """A cycle ended because the model said it was done."""
        return self.state(cycle, chat.KIND_DONE, nu.Str(FINISHED) + nu.ToStr(cycle))

    def stalled(self, cycle: nu.StrArg) -> nu.Nu:
        """A cycle ended because it ran out of passes, which is not the same."""
        return self.state(cycle, chat.KIND_FAILED, nu.Str(OUT_OF_PASSES) + nu.ToStr(cycle))

    def stuck(self, cycle: nu.StrArg, repeats: nu.IntArg, failure: nu.StrArg) -> nu.Nu:
        """A cycle ended because it kept failing the same way.

        The third way a cycle can end and the only one worth a row that says
        what went wrong, because it is the only one where the same line is
        already three rows above this one and the person needs telling that
        those three were the reason rather than a coincidence.
        """
        told = (
            nu.Str(STUCK)
            + nu.ToStr(cycle)
            + nu.Str(SAME)
            + nu.ToStr(nu.Int(repeats))
            + nu.Str(TIMES)
            + nu.Str(failure)
        )
        return self.state(cycle, chat.KIND_FAILED, clipped(told))

    def crashed(self, why: nu.StrArg) -> nu.Nu:
        """The loop itself died. Written where a turn never got to close itself."""
        return self.state(chat.CYCLE_ANSWER, chat.KIND_FAILED, nu.Str(CRASHED) + nu.ToStr(why))

    def _said(self) -> nu.Nu:
        """The model's prose from the pass before this one."""
        return memory.reply_of(self.plane_id, self.cell_id, root=self.root)

    def _outcome(self) -> nu.Nu:
        """What the pass that just ran came to."""
        return memory.outcome_of(self.plane_id, self.cell_id, root=self.root)


def asked(plane_id: nu.StrArg, cell_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """The last thing said in a chat, which is what started the turn running.

    A turn only runs while the last word was the person's, so the last message
    is theirs and nothing has to look for the newest one with a role on it.

    Empty where nothing has been said, because reading past the end of an
    empty list yields INVALID, which collapses everything composed with it.
    """
    said = nu.List(chat.messages_of(plane_id, cell_id, root=root))
    last = nu.Dict(
        nu.List(chat.messages_of(plane_id, cell_id, root=root))[nu.Len(said) - nu.Int(1)]
    )
    return nu.Str(
        nu.If(
            nu.Gt(nu.Len(said), nu.Int(0)),
            nu.ToStr(last.get_item(nu.Str("text"), nu.Str(""))),
            nu.Str(""),
        )
    )


def session_slots(panel: Panel) -> nu.Nu:
    """This chat's session, as the ref its slots hang off.

    A one line indirection that earns itself by being the only place the pass
    and the two cycles agree about where a turn's working memory is. Fresh at
    each call site, like every other address here.
    """
    return memory.session_of(panel.plane_id, panel.cell_id, root=panel.root)
