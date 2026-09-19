"""What a ``+`` makes, per group.

A group is set at birth and says which family a Plane came out of. This is
the other half of that: one entry per group, holding the Planes pressing
``+`` writes and the Cells they are seeded with. Nothing here is read again
afterwards, and nothing in the runtime ever asks a Plane what group it is in.
A group decides what is made; what is made behaves the way its props say,
like any other Plane.

Not :mod:`nuspace.ops.templates`, which is what a new *Cell* starts as. That
one is a seed for one program a person is about to replace; this one is a
whole arrangement, and the two would only share a word.

**A group makes one Plane or two.** Every group has a Plane that draws,
because a row you cannot open is not a row, and it is the one the browser
minted an id for. A group whose thing also *does* something has a second
Plane behind it that runs, and the two name each other in ``cascade_delete``,
so dropping either drops both. That is the model's "a thing that runs and a
thing that draws it are two Planes", and it costs a template rather than any
UI code.

**The Plane that runs takes its id from the Plane that draws.** Derived and
not minted, because a ``+`` has to be a pure function of its event: the only
id an event carries is the browser's, an arm that runs twice has to write one
pair rather than two, and nothing in a tree built once can mint a fresh id
per notification anyway.

**One commit.** The pair and the Cells on it land together, so nothing ever
reads a Plane whose subject is not there yet. That is why the writes come
from :func:`nuspace.ops.plane_writes` and :func:`nuspace.ops.cell_writes`
rather than from the ops that bracket themselves: a Transaction inside a
Transaction opens a second one and commits it on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import nu
from nuspace.ops import templates
from nuspace.ops.cell import cell_writes
from nuspace.ops.plane import plane_writes
from nuspace.ops.utils import atomic
from nuspace.shapes import (
    DEFAULT_GROUP,
    EXEC_ASYNC,
    EXEC_MP,
    GROUP_CHAT,
    GROUP_JOB,
    GROUP_PAGE,
    GROUPS,
    TRIGGER_MANUAL,
    TRIGGER_NAV,
    Space,
)


__all__ = [
    "CHAT",
    "CHAT_TALK",
    "JOB",
    "JOB_CODE",
    "PAGE",
    "RUNS_SUFFIX",
    "CellSeed",
    "Group",
    "PlaneSeed",
    "add",
    "defined",
    "labels",
    "resolve",
]


#: What the id of the Plane that runs is: the drawn Plane's, and this.
RUNS_SUFFIX = "_runs"

#: What :meth:`CellSeed.program` cuts a rendered program at. A byte no python
#: source holds, so the cut lands exactly where the subject's id goes and the
#: text either side is what :meth:`CellSeed.render` would have produced.
_CUT = "\x00"


@dataclass(frozen=True)
class CellSeed:
    """One Cell a Plane is seeded with: what it is called and what it runs.

    The program is a format string over ``{module}`` and ``{root}``, the
    Space's own root shape class, and ``{subject}``, the id of the Plane this
    Cell is about. A subclassed Space is a different set of addresses and a
    program naming :class:`~nuspace.shapes.Space` outright would write to the
    wrong one, which is why the root is rendered in rather than imported.
    """

    cell_id: str
    name: str
    source: str

    def render(self, subject: str, root: type[Space] = Space) -> str:
        """The program, for a subject whose id is known now."""
        return self.source.format(module=root.__module__, root=root.__name__, subject=subject)

    def program(self, subject: nu.StrArg, root: type[Space] = Space) -> nu.Nu:
        """The program, for a subject whose id only the running tree knows.

        The id is baked into the text the Cell stores rather than worked out
        by the program, so what sits in the store afterwards is an ordinary
        program naming an ordinary Plane and nothing has to remember how a
        pair was named. Plane ids never change, so baked in stays true.
        """
        parts = self.render(_CUT, root).split(_CUT)
        written = nu.Str(parts[0])
        for part in parts[1:]:
            written = nu.Add(written, nu.Add(nu.ToStr(subject), nu.Str(part)))
        return written


@dataclass(frozen=True)
class PlaneSeed:
    """One Plane a group makes: how it meets the world, and what is on it."""

    exec_mode: str
    trigger: str
    ui: bool
    editable: bool
    cells: tuple[CellSeed, ...] = ()


@dataclass(frozen=True)
class Group:
    """One group: what a person calls a section of them, and what ``+`` makes."""

    name: str
    #: What the sidebar calls the section this group's Planes are listed in.
    label: str
    #: The Plane that draws. The one the browser minted an id for and routes
    #: to the moment it is made.
    draws: PlaneSeed
    #: The Plane that does the work, where the group has one. It draws
    #: nothing; the Plane above is what shows what it is doing.
    runs: PlaneSeed | None = None


# --- the page ----------------------------------------------------------------

PAGE = Group(
    name=GROUP_PAGE,
    label="Pages",
    # One process for the whole Plane, up while somebody is looking at it,
    # drawn, and authored from inside the Viewer. It starts empty: what a page
    # is for is what a person puts on it.
    draws=PlaneSeed(exec_mode=EXEC_ASYNC, trigger=TRIGGER_NAV, ui=True, editable=True),
)


# --- the job -----------------------------------------------------------------

#: The Cell a job is seeded with, and the one its view opens. Spelled again as
#: a literal inside the template below, because a template is source text and
#: the only name in scope there is its own. ``test_groups`` holds the two
#: together.
JOB_CODE = "c_code"


_JOB_UI = '''import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from {module} import {root}


#: The job this Cell is about. Baked in when the Plane was seeded, which is
#: safe because a plane id never changes.
JOB = "{subject}"

#: The Cell on the job that holds what it does. Seeded with the job, so it is
#: there before anything opens this.
CODE = "c_code"


def table():
    """How the job is set to run, a row per prop, as a write.

    Built fresh at each call site. One node in two tree positions is one
    node, and this one is written on the way in and again on every change.
    """
    return nustd.ui.TableRef("props").set(
        nu.Dict.of(
            columns=nu.List.of("prop", "value"),
            rows=nu.List.of(
                nu.List.of(nu.Str("exec_mode"), ops.plane_exec_mode(JOB, root={root})),
                nu.List.of(nu.Str("trigger"), ops.plane_trigger(JOB, root={root})),
                nu.List.of(nu.Str("ui"), nu.ToStr(ops.plane_ui(JOB, root={root}))),
                nu.List.of(nu.Str("editable"), nu.ToStr(ops.plane_editable(JOB, root={root}))),
            ),
        )
    )


def out(plane, cell):
    """How the job is set to run, and its program in an editor.

    No name anywhere: the sidebar is where a Plane is called something, and
    saying it again at the top of the thing you just clicked is saying it
    twice.

    The editor is seeded from the store on the way in and owns the text from
    then on, so nothing here watches the program it writes: an arm that did
    would set the buffer back under the caret on every save.
    """
    code = nustd.ui.MonacoRef("code")
    prog = {root}.planes[JOB].cells[CODE].prog
    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(
        table()
        >> code.set(prog)
        >> nu.ParallelAsync(
            nu.ReactForever(code.on_change(), prog.set(nu.Str(code))),
            nu.ReactForever({root}.planes[JOB].props.on_change(), table()),
        ),
        scope={root},
    )
'''


JOB = Group(
    name=GROUP_JOB,
    label="Jobs",
    # Drawn, not authored: its Cells are the template's and a person rewriting
    # them is rewriting the view of a job rather than the job.
    draws=PlaneSeed(
        exec_mode=EXEC_ASYNC,
        trigger=TRIGGER_NAV,
        ui=True,
        editable=False,
        cells=(CellSeed(cell_id="c_ui", name="job", source=_JOB_UI),),
    ),
    # A process per Cell, up when somebody says so. It arrives holding the
    # skeleton a Cell starts as, because what the Plane above offers is an
    # editor over it and an editor wants something to open.
    runs=PlaneSeed(
        exec_mode=EXEC_MP,
        trigger=TRIGGER_MANUAL,
        ui=False,
        editable=False,
        cells=(CellSeed(cell_id=JOB_CODE, name="code", source=templates.PROGRAM.source),),
    ),
)


# --- the chat ----------------------------------------------------------------

#: The Cell a chat's runs Plane is seeded with: the one that talks to the
#: model and keeps what was said in its own state. Spelled again as a literal
#: inside the view template below, because a template is source text and the
#: only name in scope there is its own. The Cell that talks is handed its own
#: ids and names neither. ``test_chat`` holds the two spellings together.
CHAT_TALK = "c_talk"


_CHAT_UI = '''import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from {module} import {root}


#: The chat this Cell is about. Baked in when the Plane was seeded, which is
#: safe because a plane id never changes.
CHAT = "{subject}"

#: The Cell on it that talks and keeps the conversation. Seeded with the
#: chat, so it is there before anything opens this.
TALK = "c_talk"

#: What the two columns of the conversation are called.
COLUMNS = ("who", "said")

#: What the row reader binds the message it is on under.
ITEM = "_chat_line"


def timeline():
    """What was said, as rows, oldest first, as a write.

    One ref holding a list rather than a ref per message: a conversation is
    one value that grows, and a node per line would be a node to mint, root
    and take down again on every reply.

    Built fresh at each call site. One node in two tree positions is one
    node, and this one is written on the way in and again on every message.
    """
    said = nu.DictAttrRef(ITEM)
    return nustd.ui.TableRef("timeline").set(
        nu.Dict.of(
            columns=nu.List.of(nu.Str(COLUMNS[0]), nu.Str(COLUMNS[1])),
            rows=nu.Collect(
                nu.Map(
                    ops.chat.messages_of(CHAT, TALK, root={root}),
                    nu.List.of(
                        nu.ToStr(said.get_item(nu.Str("role"), nu.Str(""))),
                        nu.ToStr(said.get_item(nu.Str("text"), nu.Str(""))),
                    ),
                    key=ITEM,
                )
            ),
        )
    )


def out(plane, cell):
    """The conversation, a box to write in, and the button that sends it.

    No name anywhere: the sidebar is where a Plane is called something, and
    saying it again at the top of the thing you just clicked is saying it
    twice.

    The box is emptied after the submit and not before, because the submit is
    what reads it.
    """
    box = nustd.ui.TextAreaRef("message")
    send = nustd.ui.ButtonRef("send")
    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(
        timeline()
        # Written empty rather than left alone. A bare ref is rooted by the
        # host when something writes it, so a box nobody writes is a box
        # nobody can type in: it would first appear on the submit that reads
        # it, which is the one moment it is too late to be there.
        >> box.set(nu.Str(""))
        >> send.set_label(nu.Str("send"))
        >> nu.ParallelAsync(
            nu.ReactForever(
                send.on_click(),
                ops.chat.submit(CHAT, TALK, nu.Str(box), root={root})
                >> box.set(nu.Str("")),
            ),
            # A fresh subscription, never a term shared with the arm above:
            # two arms holding one node hold one handle, and the first of them
            # to end closes it under the other.
            nu.ReactForever(ops.chat.changed(CHAT, TALK, root={root}), timeline()),
        ),
        scope={root},
    )
'''


_CHAT_TALK = '''import nuagent

import nu
import nustd.cc
import nustd.kv
from nu.lang import ScalarQuery
from nu.lang.sentinels import EMPTY, INVALID
from nuspace import ops
from {module} import {root}


#: What the loop talks to. Claude Code rather than an api key, because a space
#: is a thing you run on the machine you are sitting at.
MODEL = "claude-opus-5"

#: Turns one message gets. Small on purpose: a question that has not been
#: answered in this many is usually one that needed splitting, and a model
#: editing a live Space is cheaper to re-ask than to let wander.
MAX_TURNS = 8

#: What the host says when a run ended without the model saying anything. The
#: host speaks here and nowhere else, and it earns its place twice: silence
#: reads as a broken space rather than as an unfinished job, and an answered
#: question is what stops this asking the same one again.
SILENT = "That run ended without an answer. Ask again, or ask for less."

#: Same, for the loop itself dying. The model's own mistakes never reach this:
#: a module that will not construct is fed back to it and the run carries on.
CRASHED = "The run crashed and stopped: "

#: What the first user message of a run says before the conversation. The ask
#: itself is the last thing in that conversation, so there is nothing to
#: restate.
OPENING = "Somebody is talking to you in a chat. Answer the last thing they said."


TASK = """\\
You are the agent inside a running nuspace, and you are one chat in it. A
person is talking to you, and everything said so far arrives as the first user
message of this run.

Do what they ask by writing programs against the space. Spend the early turns
reading -- return a program that yields what you need to know -- and write only
once you know the shape of what you are changing.

Every run ends the same way: one program that appends your answer to the
conversation and sets `Run.done`. Read "Talking to the person" below before you
write anything. Nothing you type outside a code fence is ever shown, so a run
that ends without that append is a run the person experienced as silence,
however well it went.\\
"""


#: The one thing this agent does differently from every other agent, so it
#: gets its own section rather than a bullet inside the space rules.
SPEAKING = """\\
# Talking to the person

Your reply text is not shown to anybody. Not the prose, not the explanation
around the fence, not a summary at the end. The only thing the host does with
your reply is pull the fenced block out of it and run that.

So **speaking is an action**, and you do it the same way you do everything
else -- by writing it:

```python
import nu
import nustd.mem
from nuspace import ops


class Run(nu.Shape):
    done = nustd.mem.BoolRef.slot()


def out():
    return ops.chat.say(
        "<the chat plane>",
        "<the chat cell>",
        "agent",
        "there are 3 planes: root, Notes, Ideas",
    ) >> Run.done.set(True)
```

Both ids are in the first user message of this run, copy them off it exactly.
That append is what lands in the chat. It is the same op a cron job or a
person at a REPL would use, and the chat is subscribed to that one slot, so
anything that writes there is heard. There is no separate reply channel and
there is not going to be one.

Rules:

- **Say something before you finish.** The last program of every run appends a
  message and sets `Run.done`, in that order, in one program.
- **Answer with a value you actually read, not one you remember.** If the ask
  was a question, the turn before this one is where you read the answer;
  compose the text out of that reading where you can.
- **`role` is always `"agent"`** when you are the one speaking. `"user"` is
  the person and `"system"` is the host; writing either of those is putting
  words in somebody else's mouth.
- **Say it once.** Re-running a turn because something else failed must not
  re-append what you already said. If you are unsure whether an append landed,
  read the conversation back and look.
- **Short.** One or two sentences. It is a chat, not a report. If the answer
  really is a list, a list is fine.
- **Say it when it fails, too.** If you cannot do what was asked, append that,
  with the reason, and set `Run.done`. An unfinished run that said nothing is
  the worst outcome available to you.\\
"""


#: The rules the stock surface preamble gets wrong for a durable, tagged
#: store. Placed after the surface so it reads as the correction it is.
SPACE_RULES = """\\
# Working the space

Your world is a live nuspace, and it is durable. Its store is bound tagged by
the root Shape class object itself, which makes the redeclaration rule above
**wrong for it**. Import the real class instead:

```python
from nuspace import ops
from {module} import {root}
```

A `{root}` you declare yourself is a different class object, so the tagged
store does not resolve against it: your program runs, nothing raises, and
every write lands in a store nobody reads. Import, never redeclare. `Plane`
and `Cell` are reached through `{root}`, so you rarely name them at all;
inspect them when you need to.

**Do not bracket your program.** The host already holds the atomic bracket
over the store. No `nustd.kv.auto_flow_atomic`, no `nu.With`, no `nu.Provide`.

**Prefer `nuspace.ops` to hand-written ref chains.** Each function returns a
Nu term and fixes every invariant the store has -- which Cells a Plane holds
and the order they are tiled in are two spellings of one fact, and these are
the only writers that keep them agreeing:

```python
from nuspace import ops

plane = ops.mint_ordered_id("p")   # python, at module level, not in the term


def out():
    return ops.groups.add("page", plane_id=plane, name="Notes")
```

**Read before you write.** `ops.plane_rows()`, `ops.cell_rows(plane)` and
`ops.cell_statuses(plane)` each yield a list of dicts describing what is
actually there. Returning one of those as your whole program is a good first
turn.

**A write program yields nothing.** It is a Flow, so the observation for a
turn that changed something reads `outcome: None`. That is correct, not a
failure, and not something to report or retry. A read program is the other way
round: its yield is the answer, and that is the turn whose outcome carries
something you can say out loud.\\
"""


class Bot(nu.Service):
    """The Claude Code endpoint this chat runs against."""

    ask = nustd.cc.PromptRef.method()


class Rendered(ScalarQuery):
    """A run's transcript flattened into one role-tagged prompt string.

    Every call to Claude Code is a fresh session, so the whole run has to ride
    along in the prompt. A python join in the middle of a Nu tree would make
    the turn unwalkable, so the flattening is an atom like everything else.

    This is nuagent's working memory -- what the model and the host said to
    each other -- and not the conversation, which is what the person reads.
    """

    def _compile(self, nid, children):
        (messages,) = children

        def thunk(rt):
            return _render(messages(rt))

        return thunk

    def _acompile(self, nid, children):
        (messages,) = children

        async def athunk(rt):
            return _render(await messages(rt))

        return athunk


def _render(messages):
    """Role-tagged blocks, or INVALID for anything that is not a transcript.

    Total on purpose: this runs inside a turn, and a raise here would kill the
    run rather than feed the model something it could fix.
    """
    if messages is EMPTY or messages is INVALID:
        return INVALID
    try:
        items = list(messages)
    except TypeError:
        return INVALID
    blocks = []
    for message in items:
        try:
            record = dict(message)
        except (TypeError, ValueError):
            return INVALID
        role = str(record.get("role", "user")).upper()
        blocks.append("### " + role + "\\n\\n" + str(record.get("content", "")))
    return "\\n\\n".join(blocks)


def talk(*, messages):
    """The endpoint nuagent's turn calls. It asks for ``messages``."""
    return Bot.ask(prompt=nu.Str(Rendered(messages)))


def system():
    """The whole system prompt, built against this Space's own root class.

    The surface is rendered in rather than written out, so a chat in a
    subclassed Space is told about *its* root. The two sections after it are
    nuspace's own, and the order is the argument: the correction comes after
    the thing it corrects, and how to speak comes last, because it is the rule
    a model is most likely to drop.
    """
    sections = nuagent.inserted(nuagent.DEFAULT_SECTIONS, nuagent.surface_section(({root},)))
    sections = nuagent.inserted(sections, nuagent.prompt.Section("space", lambda: SPACE_RULES))
    sections = nuagent.inserted(sections, nuagent.prompt.Section("speaking", lambda: SPEAKING))
    return nuagent.system_prompt(TASK, sections=sections)


def out(plane, cell):
    """One chat, live: answer whatever is outstanding, then wait for more.

    The conversation is in this Cell's own state, because a Cell's state is
    where a Cell's state goes, and because the Plane that draws is `nav` and
    is down whenever nobody is looking. nuagent's working memory is
    `MemSession` and lasts one run: it holds the model's raw replies and the
    host's observations, which is machinery. What the person reads is what
    the model *appended*, and the two are different substances.

    There is no submit to watch for. A chat is made at `manual` and the first
    message starts the Plane, so a Cell coming up is itself the signal, and
    everything after that arrives as a change.
    """

    def owed():
        """Whether the chat is waiting on a reply. Fresh at each call site."""
        return ops.chat.unanswered(plane, cell, root={root})

    def said():
        """What was said, as the model is shown it. Fresh at each call site."""
        return ops.chat.messages_of(plane, cell, root={root})

    def opening():
        """A run's first user message: where this chat is, and what was said.

        The ids ride in the message rather than in the system prompt because
        the prompt is a python string built once and the ids are terms the
        running tree resolves.
        """
        return nu.Dict.of(
            role="user",
            content=nu.Str(OPENING)
            + nu.Str("\\n\\nchat plane: ")
            + nu.ToStr(plane)
            + nu.Str("\\nchat cell: ")
            + nu.ToStr(cell)
            + nu.Str("\\n\\nWhat has been said, oldest first:\\n\\n")
            + nu.ToStr(nu.Repr(said())),
        )

    def run():
        """One nuagent loop over the conversation as it stands.

        Two dict fabrics, and the split is the whole of what the model can
        reach. The session is tagged, so nothing the model writes touches the
        run's own memory. The untagged one is where `Run.done` lives and where
        any `nustd.mem` the model invents lands, out of the way of the store.
        """
        loop = nuagent.agent(
            session=nuagent.MemSession,
            chat=talk,
            state=nu.Dict.of(planes=ops.plane_ids(root={root}), said=said()),
            max_turns=MAX_TURNS,
            start=nuagent.MemSession.messages.set(nu.List.of(opening())),
            # Quiet. The turn prints on the worker's own stdout, which nobody
            # is reading: a Cell is in a process of its own and what it has to
            # say reaches a person through the conversation, or through the
            # error on its row when it could not say anything at all.
            echo=False,
        )
        attempt = nu.TryCatch(
            loop
            >> nu.IfDo(
                owed(),
                ops.chat.say(plane, cell, ops.chat.ROLE_SYSTEM, SILENT, root={root}),
            ),
            catch=ops.chat.say(
                plane,
                cell,
                ops.chat.ROLE_SYSTEM,
                nu.Str(CRASHED) + nu.ToStr(nu.AttrRef("error")),
                root={root},
            ),
        )
        return nu.With(
            nu.Provide(dict, dict(), tag=nuagent.MemSession),
            nu.Provide(dict, dict()),
            nustd.cc.bind(
                Bot,
                model=MODEL,
                system_prompt=system(),
                allowed_tools=[],
                permission_mode="default",
            ),
            body=attempt,
        )

    # A program owns its own atomicity. Nothing brackets it on the way in,
    # because the host cannot see inside a program it evaluates.
    return nustd.kv.auto_flow_atomic(
        nu.ForeverDo(
            # Answer what is outstanding, then wait until something is. The
            # question is read twice and both reads earn their place: the
            # first covers the gap between a run ending and this subscribing,
            # where a message would otherwise wait for the next one; the
            # second is the wait itself, which ends on the message that makes
            # an answer owed and sits through every other write.
            nu.IfDo(owed(), run())
            >> nu.IfDo(
                nu.Not(owed()),
                nu.ReactWhile(
                    ops.chat.changed(plane, cell, root={root}), nu.Not(owed()), nu.Noop()
                ),
            )
        ),
        scope={root},
    )
'''


CHAT = Group(
    name=GROUP_CHAT,
    label="Chats",
    # Drawn, not authored, for the same reason a job's view is: its Cells are
    # the template's, and a person rewriting them is rewriting the view of a
    # conversation rather than the conversation.
    draws=PlaneSeed(
        exec_mode=EXEC_ASYNC,
        trigger=TRIGGER_NAV,
        ui=True,
        editable=False,
        cells=(CellSeed(cell_id="c_ui", name="chat", source=_CHAT_UI),),
    ),
    # A process of its own, and down until somebody talks. ``manual`` is not
    # decoration here: a chat arrives complete and idle, and the first message
    # flips this Plane to ``boot``, which is what brings the Cell up. That is
    # why a chat needs no ready flag and no submit slot -- being started *is*
    # the submit.
    runs=PlaneSeed(
        exec_mode=EXEC_MP,
        trigger=TRIGGER_MANUAL,
        ui=False,
        editable=False,
        cells=(CellSeed(cell_id=CHAT_TALK, name="talk", source=_CHAT_TALK),),
    ),
)


#: Every group, by name. Keyed by :data:`nuspace.shapes.GROUPS`, which is the
#: vocabulary and the order sections are listed in, so a group named there
#: with nothing defined here is a loud failure rather than a missing section.
_DEFINED: dict[str, Group] = {group.name: group for group in (PAGE, JOB, CHAT)}


def defined() -> tuple[Group, ...]:
    """Every group, in the order the sidebar lists their sections."""
    return tuple(_DEFINED[name] for name in GROUPS)


def labels() -> dict[str, str]:
    """What a person calls each group's section, by group name."""
    return {group.name: group.label for group in defined()}


def resolve(name: object) -> Group:
    """The group called ``name``. Anything else is the default one.

    Total on purpose. Every Plane is in a group and the default is somewhere
    a person writes and reads, so there is no value here to reject and a
    ``+`` that was asked for a word nobody knows still makes something a
    person can open.
    """
    return _DEFINED.get(str(name or ""), _DEFINED[DEFAULT_GROUP])


# --- write -------------------------------------------------------------------


def _seeded(
    seed: PlaneSeed,
    plane_id: nu.StrArg,
    *,
    group: str,
    name: nu.StrArg | None,
    subject: nu.StrArg,
    cascade_delete: list[nu.StrArg] | None,
    root: type[Space],
) -> nu.Nu:
    """One Plane a group makes, and everything on it, as writes."""
    written = plane_writes(
        plane_id=plane_id,
        name=name,
        group=group,
        exec_mode=seed.exec_mode,
        trigger=seed.trigger,
        ui=seed.ui,
        editable=seed.editable,
        cascade_delete=cascade_delete,
        root=root,
    )
    for cell in seed.cells:
        written = written >> cell_writes(
            plane_id,
            cell.program(subject, root=root),
            cell_id=cell.cell_id,
            name=cell.name,
            root=root,
        )
    return written


def _made(
    group: Group,
    plane_id: nu.StrArg,
    name: nu.StrArg | None,
    root: type[Space],
) -> nu.Nu:
    """Everything one group's ``+`` writes, as writes.

    Built fresh per call site: a group is both a case of the switch below and,
    for the default one, the branch nothing matched, and one node in two tree
    positions is one node.
    """
    drawn = _seeded(
        group.draws,
        plane_id,
        group=group.name,
        name=name,
        subject=plane_id,
        cascade_delete=None,
        root=root,
    )
    if group.runs is None:
        return drawn
    runner = nu.Add(nu.ToStr(plane_id), nu.Str(RUNS_SUFFIX))
    # The Plane that runs goes first, so the Plane the browser is about to
    # open never exists without the one it is about. Both name each other, so
    # dropping either drops both.
    return _seeded(
        group.runs,
        runner,
        group=group.name,
        name=name,
        subject=plane_id,
        cascade_delete=[plane_id],
        root=root,
    ) >> _seeded(
        group.draws,
        plane_id,
        group=group.name,
        name=name,
        subject=runner,
        cascade_delete=[runner],
        root=root,
    )


def add(
    group: nu.StrArg,
    *,
    plane_id: nu.StrArg,
    name: nu.StrArg | None = None,
    root: type[Space] = Space,
) -> nu.Nu:
    """Make whatever ``group`` says a ``+`` makes, in one commit.

    One op and not one per group, so the next group costs an entry in the
    table above and no new wiring. ``group`` is read while the tree runs,
    because a ``+`` arrives as an event carrying which section it was pressed
    under, and every group in the table is a branch of the switch.

    Args:
        group: which family to build. A word nobody knows builds the default
            one rather than nothing, for the reason in :func:`resolve`.
        plane_id: the id of the Plane that draws, which is the one that
            opens. Minted by whoever is asking, so running this twice rewrites
            one arrangement instead of making a second.
        name: what to call it. Every Plane the group makes takes the same
            name: to a person they are one thing.
        root: the Space shape class.
    """
    return atomic(
        nu.SwitchDo(
            nu.ToStr(group),
            {defn.name: _made(defn, plane_id, name, root) for defn in defined()},
            _made(resolve(None), plane_id, name, root),
        ),
        root,
    )
