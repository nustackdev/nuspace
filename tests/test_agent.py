"""The agent a chat runs, and the prose it reads.

Three things are checked here. That the term a talking Cell runs constructs
at all, and that the endpoint it runs against is the one it was handed. That
the prompt is about the Space it was built for, marks and all. And that every
program written out in the prose is a program: the prose teaches by example
and an example that will not construct teaches a model to write one that will
not either, which costs a turn every time somebody copies it.

That last one reaches two levels down. A turn's program contains the source
of the Cell it draws, as a string, so the drawn Cells are compiled and
validated out of the blocks that carry them.
"""

from __future__ import annotations

import inspect

import nu
import nustd.kv
from nuspace import ops
from nuspace.agent import cc, conversation, converse, llm, prompt, steps
from nuspace.ops import chat, groups
from nuspace.shapes import Space
from nuspace.space import store


#: The two Planes a chat is, in every test below.
UI = "p_chat"
RUNS = f"{UI}{groups.RUNS_SUFFIX}"


class Other(Space):
    """A Space of somebody else's, for the prompt to be about."""


# --- the term a talking Cell runs ----------------------------------------------


def test_the_whole_chat_constructs_and_validates():
    nu.validate(nu.compile(converse(RUNS, groups.CHAT_TALK, ui_plane_id=UI)))


def test_the_endpoint_holds_the_whole_loop_and_not_one_turn():
    """A session that lasts a turn is a cold start every turn, which is the
    whole reason this moved out of the template. The bracket has to be built
    around the loop, so the loop arrives at the endpoint as a callable and
    the endpoint decides where it goes."""
    seen = {}

    def endpoint(turns, *, system):
        seen["system"] = system
        seen["inside"] = turns(cc.ask)
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


def test_a_turn_budget_and_the_two_things_the_host_says():
    """The host speaks about the run and never about the work. Both lines are
    what stops an unanswered question putting the loop straight back round
    it."""
    assert conversation.MAX_TURNS > 0
    assert conversation.SILENT and conversation.CRASHED


# --- the prompt ----------------------------------------------------------------


def test_the_prompt_is_about_the_space_it_was_built_for():
    text = prompt.system_prompt(root=Other)
    assert prompt.ROOT_MARK not in text
    assert prompt.MODULE_MARK not in text
    assert "from tests.test_agent import Other" in text or "import Other" in text
    assert "scope=Other" in text


def test_every_section_reaches_the_model():
    text = prompt.system_prompt()
    for heading in ("# Working the space", "# Answering", "# Drawing a turn", "# Task"):
        assert heading in text
    # nuagent's own, so dropping one of ours never quietly drops all of them.
    assert "# Role" in text
    assert "# Your app surface" in text


def test_the_prose_shipped_is_the_prose_read():
    """A section named with no file behind it raises on the first prompt, and
    a file nothing names is a page nobody reads."""
    assert set(prompt.text_files()) == {f"{name}.md" for name in prompt.PROSE} | {prompt.TASK}


def test_the_prompt_teaches_the_ops_it_talks_about():
    """Every op named in the prose is one that exists. A wrong name in a
    prompt is worse than no name: the model follows it off a cliff."""
    text = prompt.system_prompt()
    for name in ("draw", "say", "step", "submit"):
        assert f"ops.chat.{name}(" in text
        assert hasattr(chat, name)


# --- the programs written out in the prose -------------------------------------


FENCE = "```"


def programs(text):
    """Every ```python block, in order."""
    return [
        chunk[len("python\n") :]
        for chunk in text.split(FENCE)[1::2]
        if chunk.startswith("python\n")
    ]


def validated(source, name):
    """Compile one block; where it is a whole Cell, run its entry point too.

    A block with no ``out`` is a fragment showing one line, and all that can
    be asked of it is that it parses. Anything with an entry point is a Cell
    somebody will copy, so it is built and validated.
    """
    if "def out(" not in source:
        compile(source, name, "exec")
        return {}
    module: dict = {}
    exec(compile(source, name, "exec"), module)  # noqa: S102
    entry = module["out"]
    took = inspect.signature(entry).parameters
    term = entry(plane=UI, cell="c_turn") if took else entry()
    nu.validate(nu.compile(term))
    return module


def test_every_program_in_the_prose_is_a_program():
    checked = 0
    for filename in prompt.text_files():
        text = prompt.read(filename)
        for index, source in enumerate(programs(text)):
            module = validated(source, f"<{filename}:{index}>")
            checked += 1
            # A turn's program carries the source of the Cells it draws, as
            # strings. Those are programs too, and they are the ones a person
            # actually ends up looking at.
            for key, value in module.items():
                if isinstance(value, str) and "def out(" in value:
                    validated(value, f"<{filename}:{index}:{key}>")
                    checked += 1
    assert checked >= 6


# --- what the host writes down -------------------------------------------------


def test_the_host_narrates_the_edges_of_a_run(tmp_path):
    """The model narrates what it did; the host narrates that there was a
    run at all. Cleared at the top of a run and never at the bottom, so the
    last run's list stays up until this one has something of its own."""
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

    write(ops.groups.add(groups.CHAT.name, plane_id=UI, name="ideas"))
    write(steps.started(RUNS, groups.CHAT_TALK))
    write(chat.step(RUNS, groups.CHAT_TALK, chat.STEP_DREW, "drew a table"))
    write(steps.ended(RUNS, groups.CHAT_TALK))
    assert read(chat.steps_of(RUNS, groups.CHAT_TALK)) == [
        {"kind": chat.STEP_THINKING, "text": steps.STARTED},
        {"kind": chat.STEP_DREW, "text": "drew a table"},
        {"kind": chat.STEP_DONE, "text": steps.ENDED},
    ]

    write(steps.started(RUNS, groups.CHAT_TALK))
    assert read(chat.steps_of(RUNS, groups.CHAT_TALK)) == [
        {"kind": chat.STEP_THINKING, "text": steps.STARTED},
    ]
