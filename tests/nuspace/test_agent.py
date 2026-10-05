"""The agent a chat runs, the two cycles it runs in, and the prose it reads.

What is checked here. That the terms a chat's Cells run construct at all, and
that the endpoint they run against is the one they were handed. That the
prompt names the Space it is about, marks and all, and teaches only ops that
exist. That every program written out in the prose is a program: the prose
teaches by example and an example that will not construct teaches a model to
write one that will not either, which costs a pass every time somebody copies
it. That a turn's working memory lands under the chat whose turn it is and
nowhere near another chat's. That the host writes the fixed machine between
the links of a pass. That the answer cycle builds a Cell before it appends
one, and that a Cell which will not build comes back to the model labelled as
the Cell rather than as the reply. And that a whole turn narrates itself as it
goes, which is the one thing only running one can show.

The program check reaches two levels down. An answer hands back the source of
the Cell it wants drawn, as a string, so the drawn Cells are compiled and
validated out of the modules that carry them.

No test here talks to a model. Every endpoint is a fake that hands back a
scripted reply, the same shape the real two hand back.
"""

from __future__ import annotations

import inspect
import subprocess
import sys
import uuid

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

import nu
import nu.prog
import nustd.kv
from nuspace import ops
from nuspace.agent import (
    cc,
    chat,
    conversation,
    converse,
    cycles,
    display,
    llm,
    perform,
    prompt,
    session,
    source,
    trace,
)
from nuspace.agent.prompt.snippets import render_snippets
from nuspace.shapes import CellState, Space, States
from nustd.cc import fabric
from nuverse.snippets import SNIPPETS, prose


#: The Plane a chat draws on, in every test below. The Plane that talks is
#: made by the first message and read back.
UI = "p_chat"

#: The panel of a chat's first turn. Built by ``submit``, addressed by
#: everything the host writes while that turn runs.
DISP = f"{chat.CHAT_DISPLAY_ID}1"

#: What the first message makes the talking Cell with. Nothing runs it here:
#: the turns below are run in this process, against the same ids.
TALK = "def out():\n    return None\n"

#: Ids for the terms that are only built, never run.
RUNS = "p_talker"

#: Every test against a store runs on both: the in memory one, and sqlite,
#: where a write bracket held across another is a lock the thread waits on.
STORES = ("memory", "sqlite")


# --- the terms a chat's Cells run ----------------------------------------------


def test_the_whole_chat_constructs_and_validates():
    nu.validate(nu.compile(converse(RUNS, chat.CHAT_TALK, ui_plane_id=UI, talk=cc.claude_code())))


def test_the_panel_constructs_and_validates():
    """Hardcoded, host owned, and called by a seeded Cell on its own two ids."""
    nu.validate(nu.compile(display(UI, DISP)))


def test_a_job_agent_is_the_same_core_with_no_drawing():
    """One core, two entry points. A job agent is the work cycle with a fixed
    task, narrating into its own Cell, and it never draws or speaks."""
    term = perform("p_job", "main", "rename the Notes plane", talk=cc.claude_code())
    nu.validate(nu.compile(term))


def test_the_endpoint_holds_the_whole_loop_and_not_one_pass():
    """A session that lasts a pass is a cold start every pass. The bracket has
    to be built around the loop, so the loop arrives at the endpoint as a
    callable and the endpoint decides where it goes."""
    seen = {}

    def endpoint(loop, *, system, plane_id, cell_id):
        seen["system"] = system
        seen["inside"] = loop(cc.ask)
        seen["cell"] = (plane_id, cell_id)
        return nu.Noop()

    converse(RUNS, chat.CHAT_TALK, ui_plane_id=UI, talk=endpoint)
    assert "# Answering" in seen["system"]
    nu.validate(nu.compile(seen["inside"]))
    # And it is told which Cell talks, which is where it keeps what it holds.
    assert seen["cell"] == (RUNS, chat.CHAT_TALK)


def test_both_endpoints_are_the_same_call():
    """Two backends, one shape. Nothing abstracts over them, so this is the
    only thing holding the two signatures together."""
    made = (
        cc.claude_code(),
        llm.served_model(base_url="http://red:11434", model="qwen3"),
    )
    for endpoint in made:
        term = endpoint(
            lambda ask: nu.print(nu.Str(nu.dict(ask(messages=[]))["text"])),
            system="s",
            plane_id=RUNS,
            cell_id=chat.CHAT_TALK,
        )
        nu.validate(nu.compile(term))


def test_the_claude_code_endpoint_is_the_one_v3_shipped():
    """One model, no tools, and permissions left at their default: the model's
    action is the Nu program it writes, and nothing else."""
    assert cc.MODEL == "claude-opus-5"
    params = inspect.signature(cc.claude_code).parameters
    assert params["allowed_tools"].default == ()
    assert params["permission_mode"].default == "default"


def test_an_endpoint_is_not_imported_until_somebody_wants_one():
    """``nustd.cc`` pulls the Claude Code SDK, which is most of a second, and
    the Cell that draws a panel reads this package for ``display`` and talks
    to no model at all. It runs in a worker launched on every navigation to
    the chat, so an eager import is that second paid by the one Cell that has
    no use for it.

    In a fresh interpreter, because this one has already imported both
    endpoints to test them and nothing can unimport a module.
    """
    probe = (
        "import sys, nuspace.agent;"
        "print(sorted(n for n in ('nuspace.agent.cc', 'nuspace.agent.llm',"
        " 'nuspace.agent.panel', 'claude_agent_sdk')"
        " if n in sys.modules))"
    )
    ran = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    assert ran.stdout.strip() == "[]"


def test_the_endpoint_table_is_the_whole_of_the_mechanism():
    """One table, read by the module ``__getattr__``, so the name still
    resolves and the import it costs is paid by whoever asked for it."""
    import nuspace.agent

    assert set(nuspace.agent.DEFERRED) == {"claude_code", "display", "served_model"}
    assert nuspace.agent.claude_code is cc.claude_code
    assert nuspace.agent.served_model is llm.served_model
    assert nuspace.agent.display is display
    with pytest.raises(AttributeError, match="no attribute"):
        nuspace.agent.nothing_like_this  # noqa: B018


def test_what_stops_a_cycle_that_is_not_going_to_end():
    """The work cycle is not capped at a number anybody would reach: long work
    is allowed to be long, and what stops it is a failure repeating. The
    answer cycle keeps a small budget, because there a pass that did not work
    is a Cell that did not build and more tries is not the fix."""
    assert chat.DEFAULT_BUDGET > cycles.ANSWER_PASSES > chat.DEFAULT_PATIENCE > 0
    assert conversation.SILENT and conversation.ASK_AGAIN and conversation.CRASHED


# --- the prompt ----------------------------------------------------------------


def test_the_prompt_names_the_space_it_is_about():
    text = prompt.system_prompt()
    assert prompt.ROOT_MARK not in text
    assert prompt.MODULE_MARK not in text
    assert f"from {Space.__module__} import Space" in text


def test_every_section_reaches_the_model():
    text = prompt.system_prompt()
    for title in (
        "# Role",
        "# The pass protocol",
        "# Finishing the work",
        "# Catalogue",
        "# Your app surface",
        "# Working the space",
        "# Snippets",
        "# A turn is two cycles",
        "# Answering",
        "# Drawing an answer",
        "# Task",
    ):
        assert title in text


def test_a_job_agent_is_not_taught_a_move_it_cannot_make():
    """It never draws and never speaks, so the two sections about doing either
    are a page of prompt teaching it something that would be refused."""
    text = prompt.system_prompt(task="rename the Notes plane", drawing=False)
    assert "# Answering" not in text
    assert "# Drawing an answer" not in text
    assert "# A turn is two cycles" in text
    assert "rename the Notes plane" in text


def test_the_prose_shipped_is_the_prose_read():
    """A section named with no file behind it raises on the first prompt, and
    a file nothing names is a page nobody reads."""
    named = {f"{name}.md" for name in prompt.PROSE} | set(prompt.MESSAGES)
    assert set(prompt.text_files()) == named


def test_the_prompt_teaches_the_ops_it_talks_about():
    """Every op named in the prose is one that exists. A wrong name in a
    prompt is worse than no name: the model follows it off a cliff."""
    text = prompt.system_prompt()
    for name in ("note", "submit", "say", "draw"):
        assert f"chat.{name}" in text
        assert hasattr(chat, name)
    assert "ops.chat" not in text
    assert "nustd.mem" not in text


def test_the_labels_the_prompt_promises_are_the_labels_the_host_writes():
    """Five ways a pass carries a complaint, and the prose names each one. A
    label a model was taught and never sees, or sees and was never taught, is
    a pass spent looking at the wrong source."""
    text = prompt.system_prompt()
    for label in source.DIAGNOSTICS:
        assert label in text


def test_the_two_cycles_are_spelled_the_way_the_rows_are():
    """The panel writes a cycle on every row and the prose tells the model
    which cycle it is in. One word, two writers."""
    text = prompt.system_prompt()
    for cycle in chat.CYCLES:
        assert cycle in text


def test_the_prompt_lists_every_snippet_and_its_ops():
    """Generated from the snippets it is handed: a snippet registered, or an
    op added, is in the next prompt with nothing written for it."""
    text = prompt.system_prompt(snippets=SNIPPETS)
    for snippet in SNIPPETS:
        assert f"## {snippet.name}  ({snippet.label})" in text
        assert snippet.description in text
    assert "from nuverse.snippets import prose" in text
    assert "prose.set_text(plane_id, cell_id, text)" in text
    assert "Replace a text cell's text" in text
    # Only what it was handed.
    alone = prompt.system_prompt(snippets=[prose.SNIPPET])
    assert "prose.set_text(plane_id, cell_id, text)" in alone
    assert "## program" not in alone
    # By default, what a space opened here registers.
    assert "prose.set_text(plane_id, cell_id, text)" in prompt.system_prompt()


def test_the_snippets_example_is_a_program():
    """The one worked example is generated, so it is checked the way the prose's are."""
    text = render_snippets(SNIPPETS)
    (src,) = programs(text)
    validated(src, "<snippets>")


def test_a_job_agent_is_taught_snippets_too():
    assert "# Snippets" in prompt.system_prompt(task="write the notes", drawing=False)


# --- the programs written out in the prose -------------------------------------


FENCE = "```"


def programs(text):
    """Every ```python block, in order."""
    return [
        chunk[len("python\n") :]
        for chunk in text.split(FENCE)[1::2]
        if chunk.startswith("python\n")
    ]


def validated(src, name):
    """Compile one block; where it is a whole Cell, run its entry point too.

    A block with no ``out`` is a fragment showing one line, and all that can
    be asked of it is that it parses. Anything with an entry point is a Cell
    somebody will copy, so it is built and validated.
    """
    if "def out(" not in src:
        compile(src, name, "exec")
        return {}
    module: dict = {}
    exec(compile(src, name, "exec"), module)  # noqa: S102
    entry = module["out"]
    took = inspect.signature(entry).parameters
    term = entry(plane=UI, cell="c_turn_1") if took else entry()
    nu.validate(nu.compile(term))
    return module


def test_every_program_in_the_prose_is_a_program():
    checked = 0
    for filename in prompt.text_files():
        text = prompt.read(filename)
        for index, src in enumerate(programs(text)):
            module = validated(src, f"<{filename}:{index}>")
            checked += 1
            # An answer carries the source of the Cell it wants drawn, as a
            # string. Those are programs too, and they are the ones a person
            # actually ends up looking at.
            for key, value in module.items():
                if isinstance(value, str) and "def out(" in value:
                    validated(value, f"<{filename}:{index}:{key}>")
                    checked += 1
    assert checked >= 20


# --- against a real store -------------------------------------------------------


async def _asked(store, said="how many planes are there"):
    """A chat somebody has spoken in, so it has a turn and a panel. The talking Plane's id."""
    await store.run(ops.add_plane(UI, backend="async", ui=True, name="ideas"))
    await store.run(chat.submit(UI, nu.Str(said), talk=TALK))
    return await store.read(chat.talker_of(UI))


def _panel(runs):
    """The panel term the host writes through, for this chat's first turn."""
    return trace.Panel(UI, runs, chat.CHAT_TALK)


async def _wrote(store, term):
    """A session write a test sets up by hand, as one commit to the state store."""
    await store.run(ops.atomic_state(term))


# --- where a turn's working memory goes ------------------------------------------


def test_the_session_routes_to_the_state_store():
    """Spelled out under the talking Cell, so it lands in the store a Cell's
    state lives in, and in no other."""
    reply = session.session_of(RUNS, chat.CHAT_TALK).reply
    assert nu.shape.root_shape(reply) is States


async def test_the_session_sits_beside_the_conversation_and_not_in_it(store):
    """Under the Cell, so one chat's turn cannot reach another's, and beside
    ``state`` rather than in it, so the writes a turn makes about itself do
    not wake the chat through the container it waits on."""
    runs = await _asked(store)
    await store.run(session.cleared(runs, chat.CHAT_TALK))
    cell = States.planes[runs].cells[chat.CHAT_TALK]
    assert sorted(await store.read(nu.list(cell.keys()))) == ["session", "state"]
    own = ops.cell_state(runs, chat.CHAT_TALK, chat.Own.state)
    assert sorted(await store.read(nu.list(own.keys()))) == sorted([chat.MESSAGES, chat.DISPLAY])


async def test_two_chats_keep_two_sessions(store):
    """The thing the nesting is for. Names alone would put both turns in one
    place and the second one would read the first one's reply."""
    mine = await _asked(store)
    await store.run(ops.add_plane("p_other", backend="async", ui=True))
    await store.run(chat.submit("p_other", nu.Str("hello"), talk=TALK))
    theirs = await store.read(chat.talker_of("p_other"))
    await _wrote(store, session.session_of(mine, chat.CHAT_TALK).reply.set("mine"))
    await _wrote(store, session.session_of(theirs, chat.CHAT_TALK).reply.set("theirs"))
    assert await store.read(session.reply_of(mine, chat.CHAT_TALK)) == "mine"
    assert await store.read(session.reply_of(theirs, chat.CHAT_TALK)) == "theirs"


async def test_an_untouched_session_reads_empty_rather_than_missing(store):
    """Where every chat starts. An unwritten leaf reads EMPTY, which flows
    through every expression it touches, so the failure would be a panel row
    that refuses to write."""
    runs = await _asked(store)
    assert await store.read(session.reply_of(runs, chat.CHAT_TALK)) == ""
    assert await store.read(session.outcome_of(runs, chat.CHAT_TALK)) == ""
    assert await store.read(session.passes_of(runs, chat.CHAT_TALK)) == 0
    assert await store.read(session.drawn_cell_of(runs, chat.CHAT_TALK)) == ""
    assert await store.read(session.said_line_of(runs, chat.CHAT_TALK)) == ""


async def test_the_reply_reads_back_as_sentences_and_not_as_the_program(store):
    """A reply is prose and then a fence, and the fence is the action. The
    panel wants the other half."""
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(
        store, slots.reply.set("I will draw a table.\n\n```python\ndef out():\n    ...\n```")
    )
    assert await store.read(session.reply_of(runs, chat.CHAT_TALK)) == "I will draw a table."

    await _wrote(store, slots.reply.set("```python\ndef out():\n    ...\n```"))
    assert await store.read(session.reply_of(runs, chat.CHAT_TALK)) == ""

    await _wrote(store, slots.reply.set("no code at all"))
    assert await store.read(session.reply_of(runs, chat.CHAT_TALK)) == "no code at all"


async def test_a_turn_starts_on_what_it_wrote_and_not_on_the_last_turn(store):
    """A turn that skipped the clear would show the last one's sentences for
    as long as its first model call took, and an answer cycle starting on the
    last turn's answer would draw it again."""
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(
        store,
        slots.reply.set("last turn")
        >> slots.outcome.set("last outcome")
        >> slots.answer.set(nu.Dict.of(cell=nu.Str("src"), said=nu.Str("said it")))
        >> slots.drawn.set(True),
    )
    await store.run(session.cleared(runs, chat.CHAT_TALK))
    assert await store.read(session.reply_of(runs, chat.CHAT_TALK)) == ""
    assert await store.read(session.outcome_of(runs, chat.CHAT_TALK)) == ""
    assert await store.read(session.drawn_cell_of(runs, chat.CHAT_TALK)) == ""
    assert await store.read(nu.Bool(slots.drawn)) is False


async def test_clearing_a_session_under_a_cell_nobody_made_makes_nothing(store):
    """A write under a missing key vivifies the row, and a chat dropped
    between a turn starting and this running would grow one out of it."""
    runs = await _asked(store)
    await store.run(session.cleared(runs, "c_nobody"))
    assert "c_nobody" not in await store.read(nu.list(States.planes[runs].cells.keys()))


# --- the fixed machine, one row at a time ---------------------------------------


async def test_the_host_writes_what_the_person_said_before_anything_runs(store):
    """The first row of every turn and the only one that needs no model call,
    so it is up while the endpoint is still being asked."""
    runs = await _asked(store)
    await store.run(_panel(runs).heard(trace.asked(runs, chat.CHAT_TALK)))
    assert await store.read(chat.trace_of(UI, DISP)) == [
        {
            "cycle": chat.CYCLE_WORK,
            "kind": chat.KIND_HEARD,
            "text": "how many planes are there",
        }
    ]


async def test_a_pass_says_which_one_it_is_against_the_ceiling(store):
    """The backstop under everything else in the panel. A model that narrates
    nothing still moves this, so a cycle is never a list that stops growing.

    The ceiling is read off the chat on every row, so a ceiling raised while a
    turn runs is a ceiling the next row shows.
    """
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    ceiling = chat.budget_of(runs, chat.CHAT_TALK)
    await _wrote(store, slots.passes.set(2))
    await store.run(_panel(runs).writing(chat.CYCLE_WORK, budget=ceiling))
    await store.run(chat.allow(runs, chat.CHAT_TALK, budget=400))
    await store.run(_panel(runs).writing(chat.CYCLE_WORK, budget=ceiling))
    assert [row["text"] for row in await store.read(chat.trace_of(UI, DISP))] == [
        f"{trace.PASS}2{trace.OF}{chat.DEFAULT_BUDGET}",
        f"{trace.PASS}2{trace.OF}400",
    ]


async def test_a_pass_that_worked_shows_what_it_came_to(store):
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(store, slots.outcome.set("['p_chat', 'p_notes']"))
    await store.run(_panel(runs).ran(chat.CYCLE_WORK))
    (row,) = await store.read(chat.trace_of(UI, DISP))
    assert row == {
        "cycle": chat.CYCLE_WORK,
        "kind": chat.KIND_RUNNING,
        "text": "['p_chat', 'p_notes']",
    }


async def test_a_pass_that_did_not_build_says_so_and_quotes_the_first_line(store):
    """The one time the outcome is worth a panel row in full. Everything after
    the first line is the diagnostic, which belongs to the model."""
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(store, slots.outcome.set(f"{source.FAILED_LABEL}: bad indent (line 3)\nand more"))
    await store.run(_panel(runs).ran(chat.CYCLE_WORK))
    (row,) = await store.read(chat.trace_of(UI, DISP))
    assert row["kind"] == chat.KIND_FAILED
    assert row["text"] == f"{source.FAILED_LABEL}: bad indent (line 3)"


async def test_a_cell_that_did_not_build_is_a_failed_row_too(store):
    """Its own label, and the panel has to know it is one of the complaints or
    a broken answer would read as an answer that worked."""
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(store, slots.outcome.set(f"{source.CELL_LABEL}: invalid syntax (line 9)"))
    await store.run(_panel(runs).ran(chat.CYCLE_ANSWER))
    (row,) = await store.read(chat.trace_of(UI, DISP))
    assert row["cycle"] == chat.CYCLE_ANSWER
    assert row["kind"] == chat.KIND_FAILED


async def test_a_long_line_is_cut_where_a_panel_can_hold_it(store):
    """A diagnostic runs to a screenful and a row is a line in a table
    somebody is watching."""
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(store, slots.reply.set("x" * (trace.LINE * 2)))
    await store.run(_panel(runs).thinking(chat.CYCLE_WORK))
    (row,) = await store.read(chat.trace_of(UI, DISP))
    assert row["text"] == "x" * trace.LINE + trace.ELLIPSIS


async def test_a_reply_that_was_all_code_says_nothing(store):
    """A blank row in a panel reads as something having gone wrong."""
    runs = await _asked(store)
    slots = session.session_of(runs, chat.CHAT_TALK)
    await _wrote(store, slots.reply.set("```python\ndef out():\n    ...\n```"))
    await store.run(_panel(runs).thinking(chat.CYCLE_WORK))
    assert await store.read(chat.trace_of(UI, DISP)) == []


# --- the check the answer cycle makes -------------------------------------------


#: A Cell that builds: what happened, and the box the next thing is typed in.
GOOD_CELL = """import nu
import nustd.ui
from nuspace import ops
from nuspace.agent import chat


def out():
    box = nustd.ui.TextAreaRef("message")
    send = nustd.ui.ButtonRef("send")
    return (
        nustd.ui.MarkdownRef("answer").set("there are 2 planes")
        >> box.set("")
        >> send.set_label("send")
        >> nu.ReactForever(send.on_click(), chat.submit(ops.Here.plane, nu.Str(box)))
    )
"""

#: A Cell that does not parse. The commonest way a model breaks one.
UNPARSED_CELL = "def out(plane, cell:\n    return None\n"

#: A Cell that parses perfectly and breaks a Nu law. The reason the check is
#: two checks: construction alone would let this one through.
UNLAWFUL_CELL = """import nu


class W(nu.Shape):
    n = nu.IntRef.slot()


def out():
    return nu.Add(W.n.set(nu.Int(1)), nu.Int(2))
"""


def _checked(cell_source):
    """Run the check over one Cell's source and give back what it came to.

    The same two catches the answer cycle puts around it, because the check
    raises rather than answering False: the diagnostic is on the error and
    the error is the whole of what the model needs.
    """
    return nu.run(
        nu.TryCatch(
            nu.TryCatch(
                nu.Str(
                    nu.If(
                        source.stands(cell_source, plane_id=UI, cell_id="c_turn_1"),
                        nu.Str(""),
                        nu.Str(""),
                    )
                ),
                catch=nu.Str(f"{source.CELL_LABEL}: ") + nu.ToStr(source.diagnostic()),
                errors=nu.prog.ConstructionError,
            ),
            catch=nu.Str(f"{source.CELL_LABEL}: ") + nu.ToStr(nu.Attr("error")),
            errors=Exception,
        )
    )[0]


def test_a_cell_that_builds_passes_the_check():
    assert _checked(GOOD_CELL) == ""


def test_a_cell_that_does_not_parse_comes_back_as_the_cell():
    """Labelled as the Cell and not as the reply. There are two pieces of
    source in an answer pass and a model told only "CONSTRUCTION FAILED"
    would go looking at the wrong one."""
    said = _checked(UNPARSED_CELL)
    assert said.startswith(source.CELL_LABEL)
    assert "does not parse" in said


def test_a_cell_that_breaks_a_law_is_caught_too():
    """The half construction cannot see. It parses, `out` returns a term, and
    the term puts a Command where a value belongs. Validating is what the host
    does before it drives anything, so a Cell that fails it is a Cell that
    fails on the screen."""
    said = _checked(UNLAWFUL_CELL)
    assert said.startswith(source.CELL_LABEL)
    assert "cannot hold" in said


# --- a whole turn, narrating itself ----------------------------------------------

#: What the model writes to end the work cycle. ``Run`` is redeclared flat,
#: which is how the model reaches the slot the loop reads, and is why that one
#: provide is left where it is.
WORKED = """import nu


class Run(nu.Shape):
    done = nu.BoolRef.slot()


def out():
    return Run.done.set(True)
"""

#: And what it hands back in the answer cycle: a value, never a write.
ANSWERED = '''import nu


CELL = """{cell}"""


def out():
    return nu.Dict.of(cell=nu.Str(CELL), said=nu.Str("there are two"))
'''.format(cell=GOOD_CELL.replace('"""', "'''"))

#: The same, holding a Cell that will not parse. The model finds out and the
#: chat is not left with a broken row on it.
BROKEN = f'''import nu


CELL = """{UNPARSED_CELL}"""


def out():
    return nu.Dict.of(cell=nu.Str(CELL), said=nu.Str("there are two"))
'''

#: What the model writes when the answer is content: a text snippet on the
#: plane that draws, its text set by the snippet's op, and the work done.
NOTED = f"""import nu
from nuspace import ops
from nuverse.snippets import prose


class Run(nu.Shape):
    done = nu.BoolRef.slot()


def out():
    noted = nu.let(
        "",
        lambda cell: (
            ops.insert_snippet("{UI}", prose.SNIPPET, into=cell)
            >> prose.set_text("{UI}", cell, "Basil likes sun")
        ),
    )
    return noted >> Run.done.set(True)
"""

#: And the answer after it: the line said, and no Cell, since the content is
#: already on the plane.
SAID_ONLY = """import nu


def out():
    return nu.Dict.of(cell=nu.Str(""), said=nu.Str("wrote it down"))
"""

#: A program that writes the talking Cell's own state, named bare the way a
#: Cell's program names it, and brackets itself with the helper the prompt
#: teaches. It lands under the talking Cell because the helper reroots it
#: there, and the host's own reroot leaves it alone.
KEPT = """import nu
import nustd.kv
import nuspace
from nuspace import ops


class Notes(nuspace.CellState):
    seen = nustd.kv.StrRef.slot()


class Run(nu.Shape):
    done = nu.BoolRef.slot()


def out():
    return ops.bracketed(Notes.seen.set("kept") >> Run.done.set(True))
"""

#: The same, writing the space too: an op of its own beside the state write,
#: and a read of what it changed, all inside the one helper.
KEPT_BOTH = f"""import nu
import nustd.kv
import nuspace
from nuspace import ops
from nuspace.shapes import Space


class Notes(nuspace.CellState):
    seen = nustd.kv.StrRef.slot()


class Run(nu.Shape):
    done = nu.BoolRef.slot()


def out():
    return ops.bracketed(
        ops.rename_plane("{UI}", "renamed")
        >> Notes.seen.set(Space.planes["{UI}"].name)
        >> Run.done.set(True)
    )
"""


class _Notes(CellState):
    """What ``KEPT`` declares, declared again here to read it from outside."""

    seen = nustd.kv.StrRef.slot()


def _fenced(*sources):
    """One reply per source, with a sentence of prose in front of each."""
    return tuple(f"Pass {index}.\n\n```python\n{one}```" for index, one in enumerate(sources, 1))


def _scripted(plane_id, cell_id, script):
    """An endpoint that reads its reply off the pass the cycle is on.

    No counter of its own: the loop keeps one and this is the one test that
    wants to know the loop keeps it honestly. The counter is per cycle, so a
    script is read per cycle too, and an index past the end floors to the last
    entry.
    """

    def endpoint(loop, *, system, **cell):
        del system, cell

        def ask(*, messages):
            del messages
            replies = nu.List.of(*[nu.Str(one) for one in script])
            # An endpoint that reads the store brackets its own read, as anything
            # a pass calls outside its brackets does.
            at = nu.Int(ops.snapshot(session.passes_of(plane_id, cell_id))) - nu.Int(1)
            return nu.Dict.of(
                text=nu.Str(
                    replies[
                        nu.If(
                            at < nu.Int(len(script)),
                            nu.If(at < nu.Int(0), nu.Int(0), at),
                            nu.Int(len(script) - 1),
                        )
                    ]
                )
            )

        return loop(ask)

    return endpoint


def _by_cycle(work, answer):
    """An endpoint that hands back ``work`` in the work cycle and ``answer`` after it.

    For a work program that writes: :func:`_scripted` would run it again on
    the answer cycle's first pass. The cycle is read off the panel, whose
    newest row the pass wrote just before asking.
    """

    def endpoint(loop, *, system, **cell):
        del system, cell

        def ask(*, messages):
            del messages
            rows = nu.List(ops.snapshot(chat.trace_of(UI, DISP)))
            cycle = nu.Str(nu.Dict(rows[-1])["cycle"])
            (said_work, said_answer) = _fenced(work, answer)
            return nu.Dict.of(text=nu.If(cycle == chat.CYCLE_ANSWER, said_answer, said_work))

        return loop(ask)

    return endpoint


async def _ran(store, runs, script, ceiling=6.0):
    """One chat, raced against a ceiling, because the loop never ends itself.

    ``script`` is the replies :func:`_scripted` reads per pass, or an endpoint.

    Inside the frame the kernel holds around a Cell run, and bracketed by
    nothing else: the chat brackets every store access itself.
    """
    endpoint = script if callable(script) else _scripted(runs, chat.CHAT_TALK, script)
    talking = converse(runs, chat.CHAT_TALK, ui_plane_id=UI, talk=endpoint)
    here = nu.Frame(ops.Here, talking, plane=runs, cell=chat.CHAT_TALK)
    await store.run(nu.Race(here, nu.DelayedDo(ceiling, nu.Noop())))


async def test_a_turn_works_then_answers_and_says_so_row_by_row(store):
    """The one thing no term on its own can show: a whole turn, and what it
    leaves in the panel on the way through.

    Everything here is what a chat does for real except the model. Two cycles,
    the prose the model wrote lifted out of each reply, a Cell built and
    checked before it landed, and the record appended in the same breath.
    """
    runs = await _asked(store)
    await _ran(store, runs, _fenced(WORKED, ANSWERED))

    kinds = [(row["cycle"], row["kind"]) for row in await store.read(chat.trace_of(UI, DISP))]
    assert kinds[0] == (chat.CYCLE_WORK, chat.KIND_HEARD)
    assert (chat.CYCLE_WORK, chat.KIND_DONE) in kinds
    assert (chat.CYCLE_ANSWER, chat.KIND_DONE) in kinds
    assert kinds[-1] == (chat.CYCLE_ANSWER, chat.KIND_DONE)
    # The work cycle's prose is what the answer cycle's first row shows: a
    # model call is one atom, so the row that goes up while a person waits is
    # written before it and carries the newest prose there is.
    assert any(kind == chat.KIND_THINKING for _, kind in kinds)

    # The answer landed as a Cell, after the panel, and the record went with
    # it in the same breath. The escape hatch went under it, which is the
    # host's and not the model's: whatever the answer offered, there is always
    # one more way to say something.
    drawn = await store.read(ops.cells(UI))
    assert drawn == [DISP, f"{cycles.TURN_ID}1", f"{chat.CHAT_OTHER_ID}1"]
    assert "MarkdownRef" in await store.read(ops.prog(UI, f"{cycles.TURN_ID}1"))
    said = await store.read(chat.messages_of(runs, chat.CHAT_TALK))
    assert [one["text"] for one in said] == ["how many planes are there", "there are two"]
    assert await store.read(chat.unanswered(runs, chat.CHAT_TALK)) is False


async def test_a_program_the_model_wrote_keeps_its_state_where_the_cell_does(store):
    """The host reroots the model's programs, and the model brackets its own
    writes. A ``CellState`` the model declares lands under the talking Cell,
    in the state store, exactly where the Cell's own program would put it."""
    runs = await _asked(store)
    await _ran(store, runs, _fenced(KEPT, ANSWERED))
    kept = ops.cell_state(runs, chat.CHAT_TALK, _Notes.seen)
    assert await store.read(kept) == "kept"


async def test_a_program_writing_state_and_the_space_finishes_its_turn(store):
    """The turn that used to hang on sqlite: the model's program writes the
    Cell's state and the space while the chat runs. No bracket of the chat's
    is open around it, so its writes and the chat's own land one after the
    other and the turn answers."""
    runs = await _asked(store)
    await _ran(store, runs, _fenced(KEPT_BOTH, ANSWERED))
    kept = ops.cell_state(runs, chat.CHAT_TALK, _Notes.seen)
    assert await store.read(kept) == "renamed"
    assert await store.read(ops.plane_title(UI)) == "renamed"
    said = await store.read(chat.messages_of(runs, chat.CHAT_TALK))
    assert [one["text"] for one in said] == ["how many planes are there", "there are two"]
    assert await store.read(chat.unanswered(runs, chat.CHAT_TALK)) is False


async def _noted(store, runs):
    """The text cell the work cycle put on the plane that draws, and its text."""
    rows = await store.read(ops.cell_rows(UI))
    (cell,) = [row["id"] for row in rows if row["props"]["made_by"] == prose.SNIPPET.name]
    return cell, await store.read(prose.text_of(UI, cell))


async def test_content_goes_in_a_snippet_and_the_answer_only_says_so(store):
    """The content is cell state, set by the snippet's op in the work cycle,
    so the answer has nothing to draw: the line lands and the turn is over."""
    runs = await _asked(store, said="note that basil likes sun")
    await _ran(store, runs, _by_cycle(NOTED, SAID_ONLY))

    cell, text = await _noted(store, runs)
    assert text == "Basil likes sun"
    # The panel, the note, the hatch: no answer Cell.
    assert await store.read(ops.cells(UI)) == [DISP, cell, f"{chat.CHAT_OTHER_ID}1"]
    said = await store.read(chat.messages_of(runs, chat.CHAT_TALK))
    assert [one["text"] for one in said] == ["note that basil likes sun", "wrote it down"]
    assert await store.read(chat.unanswered(runs, chat.CHAT_TALK)) is False
    kinds = [(row["cycle"], row["kind"]) for row in await store.read(chat.trace_of(UI, DISP))]
    assert kinds[-1] == (chat.CYCLE_ANSWER, chat.KIND_DONE)


async def test_snippets_inserted_and_a_drawn_answer_land_together(store):
    runs = await _asked(store, said="note that basil likes sun")
    await _ran(store, runs, _by_cycle(NOTED, ANSWERED))

    cell, text = await _noted(store, runs)
    assert text == "Basil likes sun"
    assert await store.read(ops.cells(UI)) == [
        DISP,
        cell,
        f"{cycles.TURN_ID}1",
        f"{chat.CHAT_OTHER_ID}1",
    ]


async def test_an_answer_with_no_line_is_not_one(store):
    """The line is the record and what wakes the chat, so a Cell alone is refused."""
    unsaid = """import nu


def out():
    return nu.Dict.of(cell=nu.Str(""), said=nu.Str(""))
"""
    runs = await _asked(store)
    await _ran(store, runs, _fenced(WORKED, unsaid))
    assert await store.read(ops.cells(UI)) == [DISP, f"{chat.CHAT_OTHER_ID}1"]
    complained = [
        row["text"]
        for row in await store.read(chat.trace_of(UI, DISP))
        if row["kind"] == chat.KIND_FAILED and row["cycle"] == chat.CYCLE_ANSWER
    ]
    assert any(one.startswith(cycles.INCOMPLETE[:40]) for one in complained)


async def test_a_broken_cell_is_not_appended_and_the_model_is_told(store):
    """The whole reason the answer cycle is a loop. A Cell is only built when
    somebody opens the chat, so a broken one appended here is a row that says
    it failed and nobody found out until a person looked."""
    runs = await _asked(store)
    await _ran(store, runs, _fenced(WORKED, BROKEN))

    # This turn's panel, and the escape hatch. Nothing the model drew, and the
    # hatch anyway: a turn that gave up is the turn a person most needs a way
    # to answer.
    assert await store.read(ops.cells(UI)) == [DISP, f"{chat.CHAT_OTHER_ID}1"]
    # And the model was told, in words that name the Cell rather than the reply.
    complained = [
        row["text"]
        for row in await store.read(chat.trace_of(UI, DISP))
        if row["kind"] == chat.KIND_FAILED and row["cycle"] == chat.CYCLE_ANSWER
    ]
    assert any(one.startswith(source.CELL_LABEL) for one in complained)
    # It failed in two different ways here, so it was never stuck: it used the
    # answer cycle's four passes, and the person is told that in those words.
    assert any(one.startswith(trace.OUT_OF_PASSES) for one in complained)
    said = (await store.read(chat.messages_of(runs, chat.CHAT_TALK)))[-1]
    assert said["role"] == chat.ROLE_SYSTEM
    assert said["text"] == (
        f"{cycles.STUCK_HEAD}{chat.CYCLE_ANSWER}{cycles.SPENT}{conversation.ASK_AGAIN}"
    )
    # The chat is no longer owed anything, or the loop would go straight back
    # round the same question.
    assert await store.read(chat.unanswered(runs, chat.CHAT_TALK)) is False


async def test_a_cycle_that_keeps_failing_the_same_way_gives_up_and_says_what_at(store):
    """The guard that replaced the pass budget, and the reason it replaced it.
    A model failing in new ways is working; one handed back the same first
    line twice has stopped reading it, and no number of further passes changes
    that. Patience is read off the chat, so this is also what says a number
    written into the store reaches the loop."""
    runs = await _asked(store)
    await store.run(chat.allow(runs, chat.CHAT_TALK, patience=2))
    await _ran(store, runs, _fenced(WORKED, BROKEN))

    rows = [
        row
        for row in await store.read(chat.trace_of(UI, DISP))
        if row["cycle"] == chat.CYCLE_ANSWER
    ]
    failed = [row["text"] for row in rows if row["kind"] == chat.KIND_FAILED]
    # Two passes, both the same complaint, and then it stopped: it never
    # reached the third of the four the answer cycle would have allowed.
    assert failed[0] == failed[1]
    assert failed[-1].startswith(trace.STUCK)
    assert f"{trace.SAME}2{trace.TIMES}" in failed[-1]
    said = (await store.read(chat.messages_of(runs, chat.CHAT_TALK)))[-1]["text"]
    assert said.startswith(f"{cycles.STUCK_HEAD}{chat.CYCLE_ANSWER}{cycles.STUCK_TIMES}2")
    assert failed[0] in said


# --- one Claude Code conversation for the life of the chat ------------------------


class _Claude:
    """The CLI as far as a chat needs it: transcripts by id, and the two refusals.

    ``--session-id`` on an id that has a transcript and ``--resume`` on one
    that has none are both errors, as they are for real. Every process answers
    from the same script, one reply per prompt in turn, so a turn is the work
    reply and then the answer.
    """

    def __init__(self, script):
        self.script = script
        self.transcripts = {}
        self.clients = []

    def info(self, sid, directory=None):
        del directory
        return object() if sid in self.transcripts else None

    def client(self, options):
        made = _Client(self, options)
        self.clients.append(made)
        return made


class _Client:
    """One ``claude`` process: the id it opened on, and every prompt it was sent."""

    def __init__(self, claude, options):
        self.claude = claude
        self.options = options
        self.sid = None
        self.prompts = []

    async def connect(self):
        held = self.claude.transcripts
        if self.options.session_id is not None:
            assert self.options.session_id not in held, "Session ID is already in use."
            self.sid = self.options.session_id
        elif self.options.resume is not None:
            assert self.options.resume in held, "No conversation found with session ID"
            self.sid = self.options.resume
        else:
            self.sid = str(uuid.uuid4())

    async def query(self, prompt):
        self.prompts.append(prompt)
        self.claude.transcripts.setdefault(self.sid, []).append(prompt)

    async def receive_response(self):
        script = self.claude.script
        text = script[(len(self.prompts) - 1) % len(script)]
        yield AssistantMessage(content=[TextBlock(text=text)], model="fake")
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id=self.sid,
            result=text,
        )

    async def disconnect(self):
        pass


@pytest.fixture
def claude(monkeypatch):
    """The fake CLI behind ``nustd.cc``. Nothing in a chat may run one-shot."""
    world = _Claude(_fenced(WORKED, ANSWERED))

    def query(**_):
        msg = "a chat prompted outside its session"
        raise AssertionError(msg)

    monkeypatch.setattr(fabric, "ClaudeSDKClient", world.client)
    monkeypatch.setattr(fabric, "get_session_info", world.info)
    monkeypatch.setattr(fabric, "query", query)
    return world


def _settled(runs):
    """Wait until the chat owes nothing.

    Polled rather than subscribed, because a subscription opened after the
    answer landed would wait for a change that already happened.
    """
    return nu.WhileDo(ops.snapshot(chat.unanswered(runs, chat.CHAT_TALK)), nu.Delay(0.02))


async def _talked(store, runs, driver, ceiling=6.0):
    """The talking Cell on Claude Code, run until ``driver`` ends: one start of the Cell."""
    talking = converse(runs, chat.CHAT_TALK, ui_plane_id=UI, talk=cc.claude_code())
    here = nu.Frame(ops.Here, talking, plane=runs, cell=chat.CHAT_TALK)
    await store.run(nu.Race(here, driver, nu.DelayedDo(ceiling, nu.Noop())))


def _answers(said):
    return [one["text"] for one in said if one["role"] != chat.ROLE_USER]


async def test_the_first_message_gives_the_chat_its_conversation_id(store, claude):
    """Minted and kept before the first prompt, and the first prompt begins
    the conversation under it rather than under one the CLI picked."""
    runs = await _asked(store)
    await _talked(store, runs, _settled(runs))

    sid = await store.read(session.sid_of(runs, chat.CHAT_TALK))
    assert str(uuid.UUID(sid)) == sid
    (client,) = claude.clients
    assert (client.options.session_id, client.options.resume) == (sid, None)
    assert _answers(await store.read(chat.messages_of(runs, chat.CHAT_TALK))) == ["there are two"]


async def test_a_later_turn_talks_on_the_same_conversation(store, claude):
    """Every turn while the Cell runs is a turn on the one process, so the
    model keeps its own context from one to the next."""
    runs = await _asked(store)
    again = chat.submit(UI, nu.Str("and now?"), talk=TALK)
    await _talked(store, runs, _settled(runs) >> again >> _settled(runs))

    sid = await store.read(session.sid_of(runs, chat.CHAT_TALK))
    (client,) = claude.clients
    assert client.sid == sid
    assert len(client.prompts) == 4
    said = await store.read(chat.messages_of(runs, chat.CHAT_TALK))
    assert _answers(said) == ["there are two", "there are two"]


async def test_a_restarted_talking_cell_resumes_its_conversation(store, claude):
    """The point of keeping the id. A Cell that comes back, for a new nuspace
    or a reboot, opens the same conversation again instead of a fresh one."""
    runs = await _asked(store)
    await _talked(store, runs, _settled(runs))
    sid = await store.read(session.sid_of(runs, chat.CHAT_TALK))

    await store.run(chat.submit(UI, nu.Str("and now?"), talk=TALK))
    await _talked(store, runs, _settled(runs))

    assert await store.read(session.sid_of(runs, chat.CHAT_TALK)) == sid
    opened, resumed = claude.clients
    assert (resumed.options.resume, resumed.options.session_id) == (sid, None)
    assert claude.transcripts[sid] == opened.prompts + resumed.prompts
    said = await store.read(chat.messages_of(runs, chat.CHAT_TALK))
    assert _answers(said) == ["there are two", "there are two"]
