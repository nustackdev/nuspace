"""A chat is a job with a label, and the conversation is what makes it one.

Three things are checked here and nothing else is. What a ``+`` makes, which
is the same pair every job makes. What a message does, which is where the one
piece of machinery a chat has lives: the first message starts the Plane and
every one after it only appends. And what the Cell asks when it comes up,
which is the whole of why a restart answers an outstanding question and never
replays a conversation it already answered.

The templates themselves are covered by ``test_groups``, which renders,
compiles and validates every seed of every group.
"""

from __future__ import annotations

import msgpack

import nu
import nustd.kv
from nuspace import ops
from nuspace.drivers import run_space
from nuspace.ops import chat, groups
from nuspace.shapes import EXEC_MP, TRIGGER_BOOT, TRIGGER_MANUAL, Space
from nuspace.space import open_space, store


#: The Plane a chat's ``+`` opens, and the one behind it, in every test below.
DRAWN = "p_chat"
RUNS = f"{DRAWN}{groups.RUNS_SUFFIX}"


def test_the_chat_view_opens_the_cell_the_chat_is_seeded_with():
    """The id is a constant on one side and a literal in source text on the
    other, and a view over a Cell that is not there draws nothing."""
    assert groups.CHAT.runs is not None
    assert [cell.cell_id for cell in groups.CHAT.runs.cells] == [groups.CHAT_TALK]
    assert f'TALK = "{groups.CHAT_TALK}"' in groups.CHAT.draws.cells[0].source


# --- against a real store ------------------------------------------------------


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

    return write, read


def _seeded(tmp_path):
    """A chat, as pressing ``+`` under the chat section makes one."""
    write, read = _space(tmp_path)
    write(ops.groups.add(groups.CHAT.name, plane_id=DRAWN, name="ideas"))
    return write, read


def test_a_chat_is_two_planes_and_the_half_that_talks_waits(tmp_path):
    write, read = _seeded(tmp_path)
    assert sorted(read(ops.plane_ids())) == sorted([DRAWN, RUNS])
    assert read(ops.plane_cascade(DRAWN)) == [RUNS]
    assert read(ops.plane_cascade(RUNS)) == [DRAWN]
    assert read(ops.plane_ui(DRAWN)) is True
    assert read(ops.plane_ui(RUNS)) is False
    # Nothing is running behind a chat nobody has talked to yet.
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_MANUAL
    assert read(ops.cell_ids(RUNS)) == [groups.CHAT_TALK]
    assert RUNS in str(read(ops.prog_of(DRAWN, groups.CHAT.draws.cells[0].cell_id)))
    assert read(chat.messages_of(RUNS, groups.CHAT_TALK)) == []
    del write


def test_dropping_either_half_of_a_chat_drops_both(tmp_path):
    write, read = _seeded(tmp_path)
    write(ops.remove_plane(DRAWN))
    assert read(ops.plane_ids()) == []

    write(ops.groups.add(groups.CHAT.name, plane_id=DRAWN, name="again"))
    write(ops.remove_plane(RUNS))
    assert read(ops.plane_ids()) == []


def test_the_first_message_starts_the_chat(tmp_path):
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("how many planes are there")))
    assert read(chat.messages_of(RUNS, groups.CHAT_TALK)) == [
        {"role": chat.ROLE_USER, "text": "how many planes are there"}
    ]
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_BOOT


def test_a_later_message_only_appends(tmp_path):
    """The flip is the first message's alone. Put the Plane back to ``manual``
    by hand, and a second message must leave it there: a chat somebody stopped
    stays stopped until somebody starts it."""
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("first")))
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("there are two")))
    write(ops.set_plane_props(RUNS, trigger=TRIGGER_MANUAL))

    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("second")))
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_MANUAL
    assert [said["text"] for said in read(chat.messages_of(RUNS, groups.CHAT_TALK))] == [
        "first",
        "there are two",
        "second",
    ]


def test_an_empty_submit_says_nothing_and_starts_nothing(tmp_path):
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("")))
    assert read(chat.messages_of(RUNS, groups.CHAT_TALK)) == []
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_MANUAL


def test_a_message_to_a_cell_nobody_made_makes_nothing(tmp_path):
    """A write under a missing key vivifies the row, so both ops are guarded
    or a dropped chat grows a Cell out of a late reply."""
    write, read = _seeded(tmp_path)
    write(chat.say(RUNS, "c_nobody", chat.ROLE_AGENT, nu.Str("ghost")))
    write(chat.submit(RUNS, "c_nobody", nu.Str("ghost")))
    assert read(ops.cell_ids(RUNS)) == [groups.CHAT_TALK]


def test_the_conversation_ships_as_values_not_views(tmp_path):
    """A list written into a kv leaf reads back as a live cursor into the
    store, which no frame can carry. Rebuilt, it is plain data."""
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("hello")))
    said = read(chat.messages_of(RUNS, groups.CHAT_TALK))
    assert all(type(one) is dict for one in said)
    assert msgpack.packb(said) is not None


# --- what a Cell asks when it comes up -----------------------------------------


def test_a_chat_nobody_started_is_owed_nothing(tmp_path):
    write, read = _seeded(tmp_path)
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False
    del write


def test_a_message_the_cell_never_heard_is_still_answered(tmp_path):
    """The Cell comes up *because* of the first message, so it cannot have
    heard the change that carried it. This is what it asks instead."""
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("what is here")))
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is True


def test_a_reboot_does_not_replay_an_answered_conversation(tmp_path):
    """The failure this guards is a chat that re-answers its whole history
    every time the Space comes back up. Nothing is owed once the last word is
    the model's, however long the conversation is."""
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("one")))
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("answered one")))
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("two")))
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("answered two")))
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False


def test_the_host_speaking_closes_an_unanswered_run(tmp_path):
    """A run that said nothing leaves the question standing, which would put
    the loop straight back round it. The host saying so is what ends that."""
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("do a thing")))
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_SYSTEM, nu.Str("that run ended")))
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False


# --- against a live Space ------------------------------------------------------

#: A talking Cell with the model taken out of it. The loop around the answer
#: is the chat template's, verbatim; only what it says is cheap, so this runs
#: in seconds and asks nothing of the network.
ACK = """import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space


def out(plane, cell):
    def owed():
        return ops.chat.unanswered(plane, cell, root=Space)

    def ack():
        return ops.chat.say(plane, cell, ops.chat.ROLE_AGENT, nu.Str("ack"), root=Space)

    return nustd.kv.auto_flow_atomic(
        nu.ForeverDo(
            nu.IfDo(owed(), ack())
            >> nu.IfDo(
                nu.Not(owed()),
                nu.ReactWhile(
                    ops.chat.changed(plane, cell, root=Space), nu.Not(owed()), nu.Noop()
                ),
            )
        ),
        scope=Space,
    )
"""


def test_a_started_chat_answers_every_message(tmp_path):
    """The one thing no term on its own can show: a Cell in a worker hearing
    a message that was written somewhere else.

    Both halves matter and they fail apart. The first answer comes from the
    Cell asking what is outstanding as it comes up, and it lands even if the
    subscription is dead. The second answer is the subscription, and the shape
    of the failure is a chat that answers once and then goes quiet forever.
    """
    path = str(tmp_path / "space")
    timeline = (
        ops.add_plane(plane_id=RUNS, exec_mode=EXEC_MP, trigger=TRIGGER_MANUAL)
        >> ops.add_cell(RUNS, ACK, cell_id=groups.CHAT_TALK)
        >> chat.submit(RUNS, groups.CHAT_TALK, nu.Str("one"))
        >> nu.DelayedDo(nu.Float(4.0), chat.submit(RUNS, groups.CHAT_TALK, nu.Str("two")))
        # Nothing left to say, and the Race ends when this branch does, which
        # is what closes the Space.
        >> nu.DelayedDo(nu.Float(4.0), nu.Noop())
    )
    nu.run_in_loop(
        open_space(
            nu.Race(run_space(), nustd.kv.auto_flow_atomic(timeline, scope=Space)), path=path
        ),
        nu.Context(),
        max_parallel=1,
    )
    said, _ = nu.run_in_loop(
        nu.With(
            store(path, root=Space),
            body=nustd.kv.Snapshot(chat.messages_of(RUNS, groups.CHAT_TALK), scope=Space),
        ),
        nu.Context(),
    )
    assert [one["text"] for one in said] == ["one", "ack", "two", "ack"]
