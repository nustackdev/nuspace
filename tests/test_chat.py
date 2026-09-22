"""A chat is a job with a label, and the conversation is what makes it one.

Five things are checked here and nothing else is. What a ``+`` makes, which is
the same pair every job makes. What a message does, which is where the one
piece of machinery a chat has lives: the first message starts the Plane and
every one after it only appends. What a submit puts up, which is the panel for
the turn, on the press that asked the question and not a model call later.
What the Cell asks when it comes up, which is the whole of why a restart
answers an outstanding question and never replays a conversation it already
answered. And what a turn leaves behind: a Cell on the Plane that draws, which
is how a model answers at all, and a trace in that turn's own panel, which is
why scrolling back to the first thing you asked still shows what was done
about it.

The templates themselves are covered by ``test_groups``, which renders,
compiles and validates every seed of every group.
"""

from __future__ import annotations

import msgpack

import nu
import nustd.kv
from nuspace import ops
from nuspace.agent import session
from nuspace.drivers import run_space
from nuspace.ops import chat, groups
from nuspace.shapes import EXEC_MP, RESTART_NO, TRIGGER_BOOT, TRIGGER_MANUAL, Space
from nuspace.space import open_space, store


#: The Plane a chat's ``+`` opens, and the one behind it, in every test below.
DRAWN = "p_chat"
RUNS = f"{DRAWN}{groups.RUNS_SUFFIX}"

#: The panel the first turn puts up, spelled out rather than read back, so a
#: change to how one is named is a change somebody has to make here too.
FIRST = f"{groups.CHAT_DISPLAY_ID}1"
SECOND = f"{groups.CHAT_DISPLAY_ID}2"


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


def _said(write, text):
    """Somebody presses send, from the box a chat was born with."""
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str(text), ui_plane_id=DRAWN))


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
    _said(write, "how many planes are there")
    assert read(chat.messages_of(RUNS, groups.CHAT_TALK)) == [
        {"role": chat.ROLE_USER, "text": "how many planes are there"}
    ]
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_BOOT


def test_a_later_message_only_appends(tmp_path):
    """The flip is the first message's alone. Put the Plane back to ``manual``
    by hand, and a second message must leave it there: a chat somebody stopped
    stays stopped until somebody starts it."""
    write, read = _seeded(tmp_path)
    _said(write, "first")
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("there are two")))
    write(ops.set_plane_props(RUNS, trigger=TRIGGER_MANUAL))

    _said(write, "second")
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_MANUAL
    assert [said["text"] for said in read(chat.messages_of(RUNS, groups.CHAT_TALK))] == [
        "first",
        "there are two",
        "second",
    ]


def test_an_empty_submit_says_nothing_and_starts_nothing(tmp_path):
    write, read = _seeded(tmp_path)
    _said(write, "")
    assert read(chat.messages_of(RUNS, groups.CHAT_TALK)) == []
    assert read(ops.plane_trigger(RUNS)) == TRIGGER_MANUAL
    # And no panel either, because a stray click is not a turn.
    assert read(ops.cell_ids(DRAWN)) == [groups.CHAT.draws.cells[0].cell_id]


def test_a_message_to_a_cell_nobody_made_makes_nothing(tmp_path):
    """A write under a missing key vivifies the row, so both ops are guarded
    or a dropped chat grows a Cell out of a late reply."""
    write, read = _seeded(tmp_path)
    write(chat.say(RUNS, "c_nobody", chat.ROLE_AGENT, nu.Str("ghost")))
    write(chat.submit(RUNS, "c_nobody", nu.Str("ghost"), ui_plane_id=DRAWN))
    assert read(ops.cell_ids(RUNS)) == [groups.CHAT_TALK]


def test_the_conversation_ships_as_values_not_views(tmp_path):
    """A list written into a kv leaf reads back as a live cursor into the
    store, which no frame can carry. Rebuilt, it is plain data."""
    write, read = _seeded(tmp_path)
    _said(write, "hello")
    said = read(chat.messages_of(RUNS, groups.CHAT_TALK))
    assert all(type(one) is dict for one in said)
    assert msgpack.packb(said) is not None


# --- what a submit puts up -----------------------------------------------------


def test_a_submit_puts_the_panel_for_the_turn_up(tmp_path):
    """The whole reason the host appends this and the agent does not. A run
    takes as long as it takes, and the panel that says what it is doing has to
    be on the screen on the press, not after the first model call."""
    write, read = _seeded(tmp_path)
    _said(write, "what is here")
    assert read(ops.cell_ids(DRAWN)) == [groups.CHAT.draws.cells[0].cell_id, FIRST]
    assert read(ops.cell_name(DRAWN, FIRST)) == f"{groups.CHAT_DISPLAY_NAME}1"
    assert read(ops.prog_of(DRAWN, FIRST)) == groups.CHAT_DISPLAY.render("")


def test_the_panel_the_running_turn_writes_into_is_the_one_just_made(tmp_path):
    """Read back rather than counted again. The op that made the Cell is the
    one that says which it is, or two callers have two answers."""
    write, read = _seeded(tmp_path)
    assert read(chat.latest_display(RUNS, groups.CHAT_TALK)) == ""
    _said(write, "one")
    assert read(chat.latest_display(RUNS, groups.CHAT_TALK)) == FIRST


def test_what_the_model_says_back_does_not_move_the_panel(tmp_path):
    """A turn is one input looped until done, however many passes it takes, so
    everything the agent says about it goes in the one panel."""
    write, read = _seeded(tmp_path)
    _said(write, "one")
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("answered")))
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_SYSTEM, nu.Str("that run ended")))
    assert read(chat.latest_display(RUNS, groups.CHAT_TALK)) == FIRST
    assert read(ops.cell_ids(DRAWN)) == [groups.CHAT.draws.cells[0].cell_id, FIRST]


def test_a_second_turn_gets_a_panel_of_its_own(tmp_path):
    write, read = _seeded(tmp_path)
    _said(write, "one")
    _said(write, "two")
    assert read(ops.cell_ids(DRAWN)) == [groups.CHAT.draws.cells[0].cell_id, FIRST, SECOND]
    assert read(chat.latest_display(RUNS, groups.CHAT_TALK)) == SECOND


def test_a_question_still_lands_where_there_is_nowhere_to_draw_it(tmp_path):
    """The append is guarded on the Plane like every other write to one. A
    chat whose drawn half was dropped is a chat nobody can watch, and losing
    what somebody asked on top of that would be losing the only record."""
    write, read = _seeded(tmp_path)
    write(chat.submit(RUNS, groups.CHAT_TALK, nu.Str("into the dark"), ui_plane_id="p_nobody"))
    assert [said["text"] for said in read(chat.messages_of(RUNS, groups.CHAT_TALK))] == [
        "into the dark"
    ]
    assert sorted(read(ops.plane_ids())) == sorted([DRAWN, RUNS])


# --- what a Cell asks when it comes up -----------------------------------------


def test_a_chat_nobody_started_is_owed_nothing(tmp_path):
    write, read = _seeded(tmp_path)
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False
    del write


def test_a_message_the_cell_never_heard_is_still_answered(tmp_path):
    """The Cell comes up *because* of the first message, so it cannot have
    heard the change that carried it. This is what it asks instead."""
    write, read = _seeded(tmp_path)
    _said(write, "what is here")
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is True


def test_a_reboot_does_not_replay_an_answered_conversation(tmp_path):
    """The failure this guards is a chat that re-answers its whole history
    every time the Space comes back up. Nothing is owed once the last word is
    the model's, however long the conversation is."""
    write, read = _seeded(tmp_path)
    _said(write, "one")
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("answered one")))
    _said(write, "two")
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_AGENT, nu.Str("answered two")))
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False


def test_a_fresh_subscription_every_time_and_two_containers_for_two_things():
    """A child scoped watch is silent in a worker, so the finest thing that can
    wake either of these is a Cell's own state. They are two Cells now: the
    conversation is the talking Cell's and a turn's trace is its panel's, which
    is what keeps the loop from waking once a pass on a row it does not read.
    Fresh nodes because a subscription is a handle and the first arm to end
    closes it under the other."""
    watch = chat.trace_changed(DRAWN, FIRST)
    assert repr(watch) == repr(Space.planes[DRAWN].cells[FIRST].state.on_change())
    assert watch is not chat.trace_changed(DRAWN, FIRST)
    assert repr(watch) != repr(chat.changed(RUNS, groups.CHAT_TALK))


def test_the_host_speaking_closes_an_unanswered_run(tmp_path):
    """A run that said nothing leaves the question standing, which would put
    the loop straight back round it. The host saying so is what ends that."""
    write, read = _seeded(tmp_path)
    _said(write, "do a thing")
    write(chat.say(RUNS, groups.CHAT_TALK, chat.ROLE_SYSTEM, nu.Str("that run ended")))
    assert read(chat.unanswered(RUNS, groups.CHAT_TALK)) is False


# --- what a turn draws ---------------------------------------------------------

#: A turn's program, as short as one can be. Nothing compiles it here: drawing
#: is a write, and a program that will not construct is a Cell that says so
#: when somebody runs it.
TURN = "def out(plane, cell):\n    return None\n"


def test_a_turn_lands_as_a_cell_after_what_the_plane_was_seeded_with(tmp_path):
    """The model answers by appending, so the view a chat is born with keeps
    the place it was born in and turns pile up behind it."""
    write, read = _seeded(tmp_path)
    seeded = read(ops.cell_ids(DRAWN))
    write(chat.draw(DRAWN, TURN, name="a table of planes"))
    drawn = read(ops.cell_ids(DRAWN))
    assert drawn[: len(seeded)] == seeded
    assert len(drawn) == len(seeded) + 1
    assert read(ops.cell_name(DRAWN, drawn[-1])) == "a table of planes"
    assert "def out" in str(read(ops.prog_of(DRAWN, drawn[-1])))


def test_a_turn_never_restarts(tmp_path):
    """A Cell's program persists and runs again on every reload, so a turn that
    did something would do it again with nobody asking."""
    write, read = _seeded(tmp_path)
    write(chat.draw(DRAWN, TURN))
    assert read(ops.cell_restart(DRAWN, read(ops.cell_ids(DRAWN))[-1])) == RESTART_NO


def test_two_turns_are_two_cells(tmp_path):
    """The id is minted per call, so the second turn appends rather than
    landing on top of the first."""
    write, read = _seeded(tmp_path)
    seeded = read(ops.cell_ids(DRAWN))
    write(chat.draw(DRAWN, TURN))
    write(chat.draw(DRAWN, TURN))
    assert len(read(ops.cell_ids(DRAWN))) == len(seeded) + 2


def test_a_turn_drawn_on_a_plane_nobody_made_draws_nothing(tmp_path):
    """A write under a missing key vivifies the row, so a chat dropped mid turn
    would grow a Plane out of the answer arriving late."""
    write, read = _seeded(tmp_path)
    write(chat.draw("p_nobody", TURN))
    assert sorted(read(ops.plane_ids())) == sorted([DRAWN, RUNS])


# --- what the agent is doing ---------------------------------------------------


def _wrote(write, cycle, kind, text):
    """One state, into whichever panel the running turn is writing into."""
    write(chat.state(DRAWN, chat.latest_display(RUNS, groups.CHAT_TALK), cycle, kind, nu.Str(text)))


def test_the_trace_reads_back_in_the_order_it_was_written(tmp_path):
    write, read = _seeded(tmp_path)
    _said(write, "what is here")
    _wrote(write, chat.CYCLE_WORK, chat.KIND_HEARD, "what is here")
    _wrote(write, chat.CYCLE_ANSWER, chat.KIND_DONE, "answer")
    assert read(chat.trace_of(DRAWN, FIRST)) == [
        {"cycle": chat.CYCLE_WORK, "kind": chat.KIND_HEARD, "text": "what is here"},
        {"cycle": chat.CYCLE_ANSWER, "kind": chat.KIND_DONE, "text": "answer"},
    ]


def test_a_note_is_the_one_row_the_model_writes(tmp_path):
    """Same list, same shape, one kind. What a program was for is known only to
    whoever wrote it, so this row is the model's and the host composes none."""
    write, read = _seeded(tmp_path)
    _said(write, "make me a table")
    write(
        chat.note(
            DRAWN,
            chat.latest_display(RUNS, groups.CHAT_TALK),
            chat.CYCLE_WORK,
            nu.Str("drew the planes table"),
        )
    )
    assert read(chat.trace_of(DRAWN, FIRST)) == [
        {"cycle": chat.CYCLE_WORK, "kind": chat.KIND_NOTE, "text": "drew the planes table"}
    ]


def test_the_turn_you_scroll_back_to_still_holds_its_own_work(tmp_path):
    """The whole of why a trace is per panel. One list that every turn emptied
    could only ever show the turn you are standing in."""
    write, read = _seeded(tmp_path)
    _said(write, "one")
    _wrote(write, chat.CYCLE_WORK, chat.KIND_RUNNING, "counted the planes")
    _said(write, "two")
    _wrote(write, chat.CYCLE_WORK, chat.KIND_RUNNING, "counted the cells")
    assert [row["text"] for row in read(chat.trace_of(DRAWN, FIRST))] == ["counted the planes"]
    assert [row["text"] for row in read(chat.trace_of(DRAWN, SECOND))] == ["counted the cells"]


def test_a_turn_that_has_written_nothing_reads_empty(tmp_path):
    """Where a panel spends the first second of its life. The leaf is unwritten
    until the run says something, and an unwritten leaf reads EMPTY, which
    collapses every Query that reaches it."""
    write, read = _seeded(tmp_path)
    _said(write, "one")
    assert read(chat.trace_of(DRAWN, FIRST)) == []


def test_a_chat_nobody_has_spoken_in_has_no_panel_to_read(tmp_path):
    """A store key may not hold an empty segment, so the id ``latest_display``
    answers before the first submit raises out of the codec unless every term
    that takes one tests it first."""
    write, read = _seeded(tmp_path)
    nowhere = chat.latest_display(RUNS, groups.CHAT_TALK)
    assert read(chat.trace_of(DRAWN, nowhere)) == []
    _wrote(write, chat.CYCLE_WORK, chat.KIND_HEARD, "into the void")
    assert read(ops.cell_ids(DRAWN)) == [groups.CHAT.draws.cells[0].cell_id]


def test_the_trace_ships_as_values_not_views(tmp_path):
    """Same failure as the conversation's, and this is the list that redraws on
    every write, so it is the one that would report itself loudest."""
    write, read = _seeded(tmp_path)
    _said(write, "one")
    _wrote(write, chat.CYCLE_ANSWER, chat.KIND_DONE, "said it")
    rows = read(chat.trace_of(DRAWN, FIRST))
    assert all(type(one) is dict for one in rows)
    assert msgpack.packb(rows) is not None


def test_a_state_written_at_a_cell_nobody_made_makes_nothing(tmp_path):
    write, read = _seeded(tmp_path)
    write(chat.state(DRAWN, "c_nobody", chat.CYCLE_WORK, chat.KIND_DONE, nu.Str("ghost")))
    write(chat.state("p_nobody", FIRST, chat.CYCLE_WORK, chat.KIND_DONE, nu.Str("ghost")))
    assert read(ops.cell_ids(DRAWN)) == [groups.CHAT.draws.cells[0].cell_id]
    assert sorted(read(ops.plane_ids())) == sorted([DRAWN, RUNS])


# --- against a live Space ------------------------------------------------------

#: A talking Cell with the model taken out of it. The loop around the answer
#: is the chat template's, verbatim; only what it says is cheap, so this runs
#: in seconds and asks nothing of the network.
#:
#: The session write rides along because it is the one part of a run whose
#: address is built rather than declared: it hangs off the Cell, so it takes
#: its tag off a parent, and the only thing that can show that resolving in a
#: worker through the proxied Navigator is a worker doing it.
#:
#: The ui plane is baked in, because that is how a chat's talking Cell learns
#: which Plane it draws into: the template carries the id as a literal.
ACK = f'''import nu
import nustd.kv
from nuspace import ops
from nuspace.agent import session
from nuspace.shapes import Space


#: The Plane this chat draws into, and where the panel for a turn is.
UI = "{DRAWN}"


def out(plane, cell):
    def owed():
        return ops.chat.unanswered(plane, cell, root=Space)

    def panel():
        return ops.chat.latest_display(plane, cell, root=Space)

    def ack():
        return (
            session.cleared(plane, cell, root=Space)
            >> session.session_of(plane, cell, root=Space).reply.set(nu.Str("acking"))
            >> ops.chat.state(
                UI,
                panel(),
                ops.chat.CYCLE_WORK,
                ops.chat.KIND_HEARD,
                nu.Str("working"),
                root=Space,
            )
            >> ops.chat.say(plane, cell, ops.chat.ROLE_AGENT, nu.Str("ack"), root=Space)
            >> ops.chat.note(UI, panel(), ops.chat.CYCLE_ANSWER, nu.Str("said it"), root=Space)
        )

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
'''


def test_a_started_chat_answers_every_message(tmp_path):
    """The one thing no term on its own can show: a Cell in a worker hearing
    a message that was written somewhere else.

    Both halves matter and they fail apart. The first answer comes from the
    Cell asking what is outstanding as it comes up, and it lands even if the
    subscription is dead. The second answer is the subscription, and the shape
    of the failure is a chat that answers once and then goes quiet forever.

    The trace rides along, and it crosses the boundary twice over. The panel
    is appended in this process, by the submit; the rows go into it from the
    worker, addressed at a Cell on a Plane that is not the one the worker runs
    on and at an id it read back out of the store rather than was handed. Two
    turns leave two panels holding one row each, which is the whole claim: a
    turn writes into its own.

    So does the run's working memory, and that one is here for a different
    reason: its address is built out of the Cell rather than declared on a
    Shape, so it takes its storage tag off a parent, and a worker reaching the
    store through a proxy is the one place that could fail to resolve.
    """
    path = str(tmp_path / "space")
    timeline = (
        # The Plane that draws, so a panel has somewhere to land. Left at
        # ``manual``: nothing on it has to run for the store to say what the
        # worker wrote into it.
        ops.add_plane(plane_id=DRAWN, trigger=TRIGGER_MANUAL)
        >> ops.add_plane(plane_id=RUNS, exec_mode=EXEC_MP, trigger=TRIGGER_MANUAL)
        >> ops.add_cell(RUNS, ACK, cell_id=groups.CHAT_TALK)
        >> chat.submit(RUNS, groups.CHAT_TALK, nu.Str("one"), ui_plane_id=DRAWN)
        >> nu.DelayedDo(
            nu.Float(4.0),
            chat.submit(RUNS, groups.CHAT_TALK, nu.Str("two"), ui_plane_id=DRAWN),
        )
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
    kept, _ = nu.run_in_loop(
        nu.With(
            store(path, root=Space),
            body=nustd.kv.Snapshot(
                nu.Dict.of(
                    said=chat.messages_of(RUNS, groups.CHAT_TALK),
                    panels=ops.cell_ids(DRAWN),
                    first=chat.trace_of(DRAWN, FIRST),
                    second=chat.trace_of(DRAWN, SECOND),
                    reply=session.reply_of(RUNS, groups.CHAT_TALK),
                ),
                scope=Space,
            ),
        ),
        nu.Context(),
    )
    assert [one["text"] for one in kept["said"]] == ["one", "ack", "two", "ack"]
    assert kept["panels"] == [FIRST, SECOND]
    assert kept["first"] == [
        {"cycle": chat.CYCLE_WORK, "kind": chat.KIND_HEARD, "text": "working"},
        {"cycle": chat.CYCLE_ANSWER, "kind": chat.KIND_NOTE, "text": "said it"},
    ]
    assert kept["second"] == kept["first"]
    assert kept["reply"] == "acking"


#: A panel with the drawing taken out of it: it counts the rows it can see
#: instead of tiling them. What is left is the one thing a panel has to do that
#: no term on its own can show, which is hear a row that was written in another
#: process.
COUNTER = f'''import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space


#: The Plane the chat draws into, and the panel on it this one is watching.
#: A real panel is handed both as its own ids; this one is watching somebody
#: else's, which is the same address either way.
UI = "{DRAWN}"
PANEL = "{FIRST}"


def out(plane, cell):
    def own():
        return Space.planes[plane].cells[cell].state

    def counted():
        return own().set_item("seen", nu.Len(nu.List(ops.chat.trace_of(UI, PANEL, root=Space))))

    def woke():
        return own().set_item("woke", nu.ToInt(own().get_item("woke", nu.Int(0))) + nu.Int(1))

    return nustd.kv.auto_flow_atomic(
        # Written on the way in, before anything is subscribed: a reader that
        # only ever writes from inside a reaction cannot tell a watch that is
        # dead from a turn that has said nothing yet. The count of wakes
        # starts at zero for the same reason, and it is kept beside the rows
        # because a watch that fires once and then goes deaf leaves the same
        # number of rows behind as one that carried.
        counted()
        >> own().set_item("woke", nu.Int(0))
        >> nu.ReactForever(ops.chat.trace_changed(UI, PANEL, root=Space), counted() >> woke()),
        scope=Space,
    )
'''


def test_a_panel_in_a_worker_hears_the_rows_a_turn_writes(tmp_path):
    """The other half of the live claim, and the half the panel is.

    A turn writes its trace from the process the agent runs in and the panel
    reads it from the process it is drawn in, so the subscription that keeps
    the panel live is proxied, and a proxied watch that does not carry is
    silent on both ends with nothing said anywhere. In process all of this
    passes whether or not it works.

    The container is the Cell's own state, which is the one scope known to
    carry. Nothing finer is wanted here: a panel's state holds its trace and
    nothing else, so the watch is already as narrow as the question.
    """
    path = str(tmp_path / "space")
    watching = "p_watch"
    seen = "c_seen"

    def wrote(text):
        return chat.state(DRAWN, FIRST, chat.CYCLE_WORK, chat.KIND_RUNNING, nu.Str(text))

    timeline = (
        ops.add_plane(plane_id=DRAWN, trigger=TRIGGER_MANUAL)
        >> ops.add_plane(plane_id=RUNS, trigger=TRIGGER_MANUAL)
        >> ops.add_cell(RUNS, "def out(plane, cell):\n    return None\n", cell_id=groups.CHAT_TALK)
        # The panel has to be there before anything watches it, which is what
        # the submit is for: it is the write that makes one.
        >> chat.submit(RUNS, groups.CHAT_TALK, nu.Str("one"), ui_plane_id=DRAWN)
        >> ops.add_plane(plane_id=watching, exec_mode=EXEC_MP, trigger=TRIGGER_BOOT)
        >> ops.add_cell(watching, COUNTER, cell_id=seen)
        # Long enough for the worker to come up and subscribe. The rows go in
        # after that, so what it ends up holding is what the watch carried and
        # not what it read on the way in.
        >> nu.DelayedDo(nu.Float(4.0), wrote("counted the planes"))
        >> nu.DelayedDo(nu.Float(2.0), wrote("counted the cells"))
        >> nu.DelayedDo(nu.Float(3.0), nu.Noop())
    )
    nu.run_in_loop(
        open_space(
            nu.Race(run_space(), nustd.kv.auto_flow_atomic(timeline, scope=Space)), path=path
        ),
        nu.Context(),
        max_parallel=1,
    )
    kept, _ = nu.run_in_loop(
        nu.With(
            store(path, root=Space),
            body=nustd.kv.Snapshot(
                nu.Dict.of(
                    seen=ops.cell_state(watching, seen),
                    rows=chat.trace_of(DRAWN, FIRST),
                ),
                scope=Space,
            ),
        ),
        nu.Context(),
    )
    assert len(kept["rows"]) == 2
    assert kept["seen"]["seen"] == 2
    # More than once, which is the difference between a live panel and one
    # that shows the first row a turn wrote and nothing after it.
    assert kept["seen"]["woke"] >= 2
