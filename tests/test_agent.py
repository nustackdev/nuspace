"""The agent a chat runs, the two cycles it runs in, and the prose it reads.

What is checked here. That the terms a chat's Cells run construct at all, and
that the endpoint they run against is the one they were handed. That the
prompt is about the Space it was built for, marks and all, and teaches only
ops that exist. That every program written out in the prose is a program: the
prose teaches by example and an example that will not construct teaches a
model to write one that will not either, which costs a pass every time
somebody copies it. That a turn's working memory lands under the chat whose
turn it is and nowhere near another chat's. That the host writes the fixed
machine between the links of a pass. That the answer cycle builds a Cell
before it appends one, and that a Cell which will not build comes back to the
model labelled as the Cell rather than as the reply. And that a whole turn
narrates itself as it goes, which is the one thing only running one can show.

The program check reaches two levels down. An answer hands back the source of
the Cell it wants drawn, as a string, so the drawn Cells are compiled and
validated out of the modules that carry them.
"""

from __future__ import annotations

import inspect
import subprocess
import sys

import pytest

import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from nuspace.agent import (
    cc,
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
from nuspace.ops import chat, groups
from nuspace.shapes import Space
from nuspace.space import store
from nuspace.web.utils import CellRoot
from nustd.ui.core import SectionRef


#: The two Planes a chat is, in every test below.
UI = "p_chat"
RUNS = f"{UI}{groups.RUNS_SUFFIX}"

#: The panel of a chat's first turn. Built by ``submit``, addressed by
#: everything the host writes while that turn runs.
DISP = f"{groups.CHAT_DISPLAY_ID}1"

#: The one Cell a chat is born with, and a literal on both sides: the
#: template names it in source text and nothing exports it.
CHAT_INPUT = "c_input"


class Other(Space):
    """A Space of somebody else's, for the prompt to be about."""


# --- the terms a chat's Cells run ----------------------------------------------


def test_the_whole_chat_constructs_and_validates():
    nu.validate(nu.compile(converse(RUNS, groups.CHAT_TALK, ui_plane_id=UI)))


def test_the_panel_constructs_and_validates():
    """Hardcoded, host owned, and called by a seeded Cell on its own two ids."""
    nu.validate(nu.compile(display(UI, DISP)))


def test_a_job_agent_is_the_same_core_with_no_drawing():
    """One core, two entry points. A job agent is the work cycle with a fixed
    task, narrating into its own Cell, and it never draws or speaks."""
    nu.validate(nu.compile(perform("p_job_runs", groups.JOB_CODE, "rename the Notes plane")))


def test_the_endpoint_holds_the_whole_loop_and_not_one_pass():
    """A session that lasts a pass is a cold start every pass, which is the
    whole reason this moved out of the template. The bracket has to be built
    around the loop, so the loop arrives at the endpoint as a callable and
    the endpoint decides where it goes."""
    seen = {}

    def endpoint(loop, *, system):
        seen["system"] = system
        seen["inside"] = loop(cc.ask)
        return nu.Noop()

    converse(RUNS, groups.CHAT_TALK, ui_plane_id=UI, talk=endpoint)
    assert "# Answering" in seen["system"]
    nu.validate(nu.compile(seen["inside"]))


def test_both_endpoints_are_the_same_call():
    """Two backends, one shape. Nothing abstracts over them, so this is the
    only thing holding the two signatures together."""
    made = (
        cc.claude_code(),
        llm.served_model(base_url="http://red:11434", model="qwen3"),
    )
    for endpoint in made:
        term = endpoint(lambda ask: nu.print(nu.Str(nu.dict(ask(messages=[]))["text"])), system="s")
        nu.validate(nu.compile(term))


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
        " 'nuspace.agent.panel', 'claude_agent_sdk', 'nustd.ui')"
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


def test_the_prompt_is_about_the_space_it_was_built_for():
    text = prompt.system_prompt(root=Other)
    assert prompt.ROOT_MARK not in text
    assert prompt.MODULE_MARK not in text
    assert "from tests.test_agent import Other" in text or "import Other" in text
    assert "scope=Other" in text


def test_every_section_reaches_the_model():
    text = prompt.system_prompt()
    for heading in (
        "# Role",
        "# The pass protocol",
        "# Finishing the work",
        "# Catalogue",
        "# Your app surface",
        "# Working the space",
        "# A turn is two cycles",
        "# Answering",
        "# Drawing an answer",
        "# Task",
    ):
        assert heading in text


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
        assert f"ops.chat.{name}" in text
        assert hasattr(chat, name)


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


def _space(tmp_path):
    """A Space on disk, and the two calls that write it and read it back."""
    path = str(tmp_path / "space")

    def write(tree):
        nu.run_in_loop(
            nu.With(store(path, root=Space), body=nustd.kv.auto_flow_atomic(tree, scope=Space)),
            nu.Context(),
        )

    def read(tree):
        value, _ = nu.run_in_loop(
            nu.With(store(path, root=Space), body=nustd.kv.Snapshot(tree, scope=Space)),
            nu.Context(),
        )
        return value

    return path, write, read


def _seeded(tmp_path):
    """A chat, as pressing ``+`` under the chat section makes one."""
    path, write, read = _space(tmp_path)
    write(ops.groups.add(groups.CHAT.name, plane_id=UI, name="ideas"))
    return path, write, read


def _asked(tmp_path, said="how many planes are there"):
    """A chat somebody has spoken in, so it has a turn and a panel."""
    path, write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str(said), ui_plane_id=UI))
    return path, write, read


def _panel():
    """The panel term the host writes through, for this chat's first turn."""
    return trace.Panel(UI, RUNS, groups.CHAT_TALK, Space)


# --- where a turn's working memory goes ------------------------------------------


def test_a_cell_gets_its_ui_refs_rooted_and_never_its_store_refs():
    """The whole reason :mod:`nuspace.agent.session` spells an address out.

    A Cell's program is loaded through a rewrite that splices bare chains
    under the Cell, and it is tempting to read that as scoping anything a
    program names. It is not: ``rooted`` exempts every chain that is not a ui
    ref, which is what keeps a Cell's store writes off the browser's tree and
    is therefore never going to change. So a session named bare inside a chat
    stays bare, and two chats would write one place."""
    rewrite = CellRoot(SectionRef("viewer", section_cls=nustd.ui.Column), groups.CHAT_TALK)
    stored = Space.planes[RUNS].name.set(nu.Str("ideas"))
    assert rewrite(stored) is stored
    drawn = nustd.ui.TextAreaRef("message").set(nu.Str(""))
    assert rewrite(drawn) is not drawn


def test_the_session_is_tagged_by_this_space_and_not_by_its_own_shape():
    """A chain rooted on the Session Shape itself asks for a Navigator tagged
    with that Shape, and the only one bound here is the Space's."""
    assert session.session_of(RUNS, groups.CHAT_TALK).reply._root_shape is Space


def test_the_session_hangs_off_the_cell_that_talks(tmp_path):
    """Under the Cell, so one chat's turn cannot reach another's, and beside
    ``state`` rather than in it, so the writes a turn makes about itself do
    not wake the chat through the container it waits on."""
    _, write, read = _asked(tmp_path)
    write(session.cleared(RUNS, groups.CHAT_TALK))
    cell = Space.planes[RUNS].cells[groups.CHAT_TALK]
    assert session.SESSION in read(nu.list(cell.keys()))
    assert session.SESSION not in read(nu.list(cell.state.keys()))
    assert sorted(read(nu.list(cell.state.keys()))) == sorted([chat.MESSAGES, chat.DISPLAY])


def test_two_chats_keep_two_sessions(tmp_path):
    """The thing the nesting is for. Names alone would put both turns in one
    place and the second one would read the first one's reply."""
    _, write, read = _seeded(tmp_path)
    other = "p_other"
    write(ops.groups.add(groups.CHAT.name, plane_id=other, name="other"))
    other_runs = f"{other}{groups.RUNS_SUFFIX}"

    write(session.session_of(RUNS, groups.CHAT_TALK).reply.set(nu.Str("mine")))
    write(session.session_of(other_runs, groups.CHAT_TALK).reply.set(nu.Str("theirs")))
    assert read(session.reply_of(RUNS, groups.CHAT_TALK)) == "mine"
    assert read(session.reply_of(other_runs, groups.CHAT_TALK)) == "theirs"


def test_an_untouched_session_reads_empty_rather_than_invalid(tmp_path):
    """Where every chat starts. An unwritten leaf reads EMPTY and every Query
    touching EMPTY collapses to INVALID, which writes nothing and raises
    nothing, so the failure would be a panel that silently stops."""
    _, write, read = _seeded(tmp_path)
    assert read(session.reply_of(RUNS, groups.CHAT_TALK)) == ""
    assert read(session.outcome_of(RUNS, groups.CHAT_TALK)) == ""
    assert read(session.passes_of(RUNS, groups.CHAT_TALK)) == 0
    assert read(session.drawn_cell_of(RUNS, groups.CHAT_TALK)) == ""
    assert read(session.said_line_of(RUNS, groups.CHAT_TALK)) == ""
    del write


def test_the_reply_reads_back_as_sentences_and_not_as_the_program(tmp_path):
    """A reply is prose and then a fence, and the fence is the action. The
    panel wants the other half."""
    _, write, read = _seeded(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(slots.reply.set(nu.Str("I will draw a table.\n\n```python\ndef out():\n    ...\n```")))
    assert read(session.reply_of(RUNS, groups.CHAT_TALK)) == "I will draw a table."

    write(slots.reply.set(nu.Str("```python\ndef out():\n    ...\n```")))
    assert read(session.reply_of(RUNS, groups.CHAT_TALK)) == ""

    write(slots.reply.set(nu.Str("no code at all")))
    assert read(session.reply_of(RUNS, groups.CHAT_TALK)) == "no code at all"


def test_a_turn_starts_on_what_it_wrote_and_not_on_the_last_turn(tmp_path):
    """A turn that skipped the clear would show the last one's sentences for
    as long as its first model call took, and an answer cycle starting on the
    last turn's answer would draw it again."""
    _, write, read = _seeded(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(
        slots.reply.set(nu.Str("last turn"))
        >> slots.outcome.set(nu.Str("last outcome"))
        >> slots.answer.set(nu.Dict.of(cell=nu.Str("src"), said=nu.Str("said it")))
        >> slots.drawn.set(nu.Bool(True))
    )
    write(session.cleared(RUNS, groups.CHAT_TALK))
    assert read(session.reply_of(RUNS, groups.CHAT_TALK)) == ""
    assert read(session.outcome_of(RUNS, groups.CHAT_TALK)) == ""
    assert read(session.drawn_cell_of(RUNS, groups.CHAT_TALK)) == ""
    assert read(nu.Bool(slots.drawn)) is False


def test_clearing_a_session_under_a_cell_nobody_made_makes_nothing(tmp_path):
    """A write under a missing key vivifies the row, and a chat dropped
    between a turn starting and this running would grow one out of it."""
    _, write, read = _seeded(tmp_path)
    write(session.cleared(RUNS, "c_nobody"))
    assert read(ops.cell_ids(RUNS)) == [groups.CHAT_TALK]


# --- the fixed machine, one row at a time ---------------------------------------


def test_the_host_writes_what_the_person_said_before_anything_runs(tmp_path):
    """The first row of every turn and the only one that needs no model call,
    so it is up while the endpoint is still being asked."""
    _, write, read = _asked(tmp_path)
    panel = _panel()
    write(panel.heard(trace.asked(RUNS, groups.CHAT_TALK)))
    assert read(chat.trace_of(UI, DISP)) == [
        {
            "cycle": chat.CYCLE_WORK,
            "kind": chat.KIND_HEARD,
            "text": "how many planes are there",
        }
    ]


def test_a_pass_says_which_one_it_is_against_the_ceiling(tmp_path):
    """The backstop under everything else in the panel. A model that narrates
    nothing still moves this, so a cycle is never a list that stops growing.

    The ceiling is read off the chat on every row, so a ceiling raised while a
    turn runs is a ceiling the next row shows.
    """
    _, write, read = _asked(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    ceiling = chat.budget_of(RUNS, groups.CHAT_TALK)
    write(slots.passes.set(nu.Int(2)))
    write(_panel().writing(chat.CYCLE_WORK, budget=ceiling))
    write(chat.allow(RUNS, groups.CHAT_TALK, budget=400))
    write(_panel().writing(chat.CYCLE_WORK, budget=ceiling))
    assert [row["text"] for row in read(chat.trace_of(UI, DISP))] == [
        f"{trace.PASS}2{trace.OF}{chat.DEFAULT_BUDGET}",
        f"{trace.PASS}2{trace.OF}400",
    ]


def test_a_pass_that_worked_shows_what_it_came_to(tmp_path):
    _, write, read = _asked(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(slots.outcome.set(nu.Str("['p_chat', 'p_notes']")))
    write(_panel().ran(chat.CYCLE_WORK))
    (row,) = read(chat.trace_of(UI, DISP))
    assert row == {
        "cycle": chat.CYCLE_WORK,
        "kind": chat.KIND_RUNNING,
        "text": "['p_chat', 'p_notes']",
    }


def test_a_pass_that_did_not_build_says_so_and_quotes_the_first_line(tmp_path):
    """The one time the outcome is worth a panel row in full. Everything after
    the first line is the diagnostic, which belongs to the model."""
    _, write, read = _asked(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(slots.outcome.set(nu.Str(f"{source.FAILED_LABEL}: bad indent (line 3)\nand more")))
    write(_panel().ran(chat.CYCLE_WORK))
    (row,) = read(chat.trace_of(UI, DISP))
    assert row["kind"] == chat.KIND_FAILED
    assert row["text"] == f"{source.FAILED_LABEL}: bad indent (line 3)"


def test_a_cell_that_did_not_build_is_a_failed_row_too(tmp_path):
    """Its own label, and the panel has to know it is one of the complaints or
    a broken answer would read as an answer that worked."""
    _, write, read = _asked(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(slots.outcome.set(nu.Str(f"{source.CELL_LABEL}: invalid syntax (line 9)")))
    write(_panel().ran(chat.CYCLE_ANSWER))
    (row,) = read(chat.trace_of(UI, DISP))
    assert row["cycle"] == chat.CYCLE_ANSWER
    assert row["kind"] == chat.KIND_FAILED


def test_a_long_line_is_cut_where_a_panel_can_hold_it(tmp_path):
    """A diagnostic runs to a screenful and a row is a line in a table
    somebody is watching."""
    _, write, read = _asked(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(slots.reply.set(nu.Str("x" * (trace.LINE * 2))))
    write(_panel().thinking(chat.CYCLE_WORK))
    (row,) = read(chat.trace_of(UI, DISP))
    assert row["text"] == "x" * trace.LINE + trace.ELLIPSIS


def test_a_reply_that_was_all_code_says_nothing(tmp_path):
    """A blank row in a panel reads as something having gone wrong."""
    _, write, read = _asked(tmp_path)
    slots = session.session_of(RUNS, groups.CHAT_TALK)
    write(slots.reply.set(nu.Str("```python\ndef out():\n    ...\n```")))
    write(_panel().thinking(chat.CYCLE_WORK))
    assert read(chat.trace_of(UI, DISP)) == []


def test_a_row_written_before_anybody_spoke_goes_nowhere(tmp_path):
    """There is no panel until a submit makes one, and the id reads back
    empty. Every write is guarded against it rather than raising out of the
    codec on an empty key segment."""
    _, write, read = _seeded(tmp_path)
    write(_panel().heard(nu.Str("nobody said this")))
    assert read(chat.latest_display(RUNS, groups.CHAT_TALK)) == ""
    assert read(ops.cell_ids(UI)) == [CHAT_INPUT]


# --- the check the answer cycle makes -------------------------------------------


#: A Cell that builds: what happened, and the box the next thing is typed in.
GOOD_CELL = f"""import nu
import nustd.kv
import nustd.ui
from nuspace import ops
from nuspace.shapes import Space


def out(plane, cell):
    box = nustd.ui.TextAreaRef("message")
    send = nustd.ui.ButtonRef("send")
    return nustd.kv.auto_flow_atomic(
        nustd.ui.MarkdownRef("answer").set(nu.Str("there are 2 planes"))
        >> box.set(nu.Str(""))
        >> send.set_label(nu.Str("send"))
        >> nu.ReactForever(
            send.on_click(),
            ops.chat.submit("{RUNS}", "{groups.CHAT_TALK}", nu.Str(box), ui_plane_id=plane, root=Space),
        ),
        scope=Space,
    )
"""

#: A Cell that does not parse. The commonest way a model breaks one.
UNPARSED_CELL = "def out(plane, cell:\n    return None\n"

#: A Cell that parses perfectly and breaks a Nu law. The reason the check is
#: two checks: construction alone would let this one through.
UNLAWFUL_CELL = """import nu
import nustd.mem


class W(nu.Shape):
    n = nustd.mem.IntRef.slot()


def out(plane, cell):
    return nu.Add(W.n.set(nu.Int(1)), nu.Int(2))
"""


def _checked(cell_source):
    """Run the check over one Cell's source and give back what it came to.

    The same two catches the answer cycle puts around it, because the check
    raises rather than answering False: the diagnostic is on the error and
    the error is the whole of what the model needs.
    """
    import nu.prog

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
            catch=nu.Str(f"{source.CELL_LABEL}: ") + nu.ToStr(nu.AttrRef("error")),
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
import nustd.mem


class Run(nu.Shape):
    done = nustd.mem.BoolRef.slot()


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

    def endpoint(loop, *, system):
        del system

        def ask(*, messages):
            del messages
            replies = nu.List.of(*[nu.Str(one) for one in script])
            at = session.passes_of(plane_id, cell_id) - nu.Int(1)
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


def _ran(path, endpoint, ceiling=6.0):
    """One chat, raced against a ceiling, because the loop never ends itself."""
    nu.run_in_loop(
        nu.With(
            store(path, root=Space),
            body=nu.Race(
                converse(RUNS, groups.CHAT_TALK, ui_plane_id=UI, talk=endpoint),
                nu.DelayedDo(nu.Float(ceiling), nu.Noop()),
            ),
        ),
        nu.Context(),
        max_parallel=1,
    )


def test_a_turn_works_then_answers_and_says_so_row_by_row(tmp_path):
    """The one thing no term on its own can show: a whole turn, and what it
    leaves in the panel on the way through.

    Everything here is what a chat does for real except the model. Two cycles,
    the prose the model wrote lifted out of each reply, a Cell built and
    checked before it landed, and the record appended in the same breath.
    """
    path, write, read = _asked(tmp_path)
    _ran(path, _scripted(RUNS, groups.CHAT_TALK, _fenced(WORKED, ANSWERED)))

    kinds = [(row["cycle"], row["kind"]) for row in read(chat.trace_of(UI, DISP))]
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
    drawn = read(ops.cell_ids(UI))
    assert drawn == [CHAT_INPUT, DISP, f"{cycles.TURN_ID}1", f"{groups.CHAT_OTHER_ID}1"]
    assert "MarkdownRef" in str(read(ops.prog_of(UI, f"{cycles.TURN_ID}1")))
    assert [one["text"] for one in read(chat.messages_of(RUNS, groups.CHAT_TALK))] == [
        "how many planes are there",
        "there are two",
    ]
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False
    del write


def test_a_broken_cell_is_not_appended_and_the_model_is_told(tmp_path):
    """The whole reason the answer cycle is a loop. A Cell is only built when
    somebody opens the chat, so a broken one appended here is a row that says
    it failed and nobody found out until a person looked."""
    path, write, read = _asked(tmp_path)
    _ran(path, _scripted(RUNS, groups.CHAT_TALK, _fenced(WORKED, BROKEN)))

    # The seeded input, this turn's panel, and the escape hatch. Nothing the
    # model drew, and the hatch anyway: a turn that gave up is the turn a
    # person most needs a way to answer.
    assert read(ops.cell_ids(UI)) == [CHAT_INPUT, DISP, f"{groups.CHAT_OTHER_ID}1"]
    # And the model was told, in words that name the Cell rather than the reply.
    complained = [
        row["text"]
        for row in read(chat.trace_of(UI, DISP))
        if row["kind"] == chat.KIND_FAILED and row["cycle"] == chat.CYCLE_ANSWER
    ]
    assert any(one.startswith(source.CELL_LABEL) for one in complained)
    # It failed in two different ways here, so it was never stuck: it used the
    # answer cycle's four passes, and the person is told that in those words.
    assert any(one.startswith(trace.OUT_OF_PASSES) for one in complained)
    said = read(chat.messages_of(RUNS, groups.CHAT_TALK))[-1]
    assert said["role"] == chat.ROLE_SYSTEM
    assert said["text"] == (
        f"{cycles.STUCK_HEAD}{chat.CYCLE_ANSWER}{cycles.SPENT}{conversation.ASK_AGAIN}"
    )
    # The chat is no longer owed anything, or the loop would go straight back
    # round the same question.
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False
    del write


def test_a_cycle_that_keeps_failing_the_same_way_gives_up_and_says_what_at(tmp_path):
    """The guard that replaced the pass budget, and the reason it replaced it.
    A model failing in new ways is working; one handed back the same first
    line twice has stopped reading it, and no number of further passes changes
    that. Patience is read off the chat, so this is also what says a number
    written into the store reaches the loop."""
    path, write, read = _asked(tmp_path)
    write(chat.allow(RUNS, groups.CHAT_TALK, patience=2))
    _ran(path, _scripted(RUNS, groups.CHAT_TALK, _fenced(WORKED, BROKEN)))

    rows = [row for row in read(chat.trace_of(UI, DISP)) if row["cycle"] == chat.CYCLE_ANSWER]
    failed = [row["text"] for row in rows if row["kind"] == chat.KIND_FAILED]
    # Two passes, both the same complaint, and then it stopped: it never
    # reached the third of the four the answer cycle would have allowed.
    assert failed[0] == failed[1]
    assert failed[-1].startswith(trace.STUCK)
    assert f"{trace.SAME}2{trace.TIMES}" in failed[-1]
    said = read(chat.messages_of(RUNS, groups.CHAT_TALK))[-1]["text"]
    assert said.startswith(f"{cycles.STUCK_HEAD}{chat.CYCLE_ANSWER}{cycles.STUCK_TIMES}2")
    assert failed[0] in said
    del write
