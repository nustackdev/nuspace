"""A chat is two Planes, and the conversation is what makes it one.

Five things are checked here and nothing else is. What the first message
makes, which is the Plane that talks, nested under the one that draws and
started. What a message does after that, which is only append. What a submit
puts up, which is the panel for the turn, on the press that asked the question
and not a model call later. What the Cell asks when it comes up, which is the
whole of why a restart answers an outstanding question and never replays a
conversation it already answered. And what a turn leaves behind: a Cell on the
Plane that draws, which is how a model answers at all, and a trace in that
turn's own panel, which is why scrolling back to the first thing you asked
still shows what was done about it.

The ops run against the in memory store. The last two tests run a talking Cell
and a panel on real workers, because a watch that does not carry to a worker
is silent on both ends and only a worker can show it carries.
"""

from __future__ import annotations

import asyncio

import msgpack
import pytest
from _support.kernel import opened

import nu
import nustd.kv
from nuspace import ops
from nuspace.agent import chat, session
from nuspace.shapes import CellState, Reroot, Space, States
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nuspace.system.services import init


#: Run on both backends: in memory, and the space's sqlite files.
STORES = ("memory", "sqlite")

#: The Plane a chat's ``+`` opens, in every test below.
UI = "p_chat"

#: What the first message makes the talking Cell with. Nothing runs it here:
#: the ops are what is under test, and they never look inside it.
TALK = "def out():\n    return None\n"

#: The panel the first turn puts up, spelled out rather than read back, so a
#: change to how one is named is a change somebody has to make here too.
FIRST = f"{UI}_{chat.CHAT_DISPLAY_ID}1"
SECOND = f"{UI}_{chat.CHAT_DISPLAY_ID}2"

#: A deadline for the tests on real workers. Met early, it costs nothing.
SLOW = 20.0


async def _seeded(store):
    """A chat, as pressing ``+`` makes one: a Plane that draws and nothing behind it."""
    await store.run(ops.add_plane(UI, backend="async", ui=True, name="ideas", made_by="cc_chat"))


async def _said(store, text, ui=UI):
    """Somebody presses send."""
    await store.run(chat.submit(ui, nu.Str(text), talk=TALK))


async def _talker(store):
    return await store.read(chat.talker_of(UI))


async def _messages(store):
    return await store.read(chat.messages_of(chat.talk_of(await _talker(store))))


# --- the pair -------------------------------------------------------------------


async def test_a_chat_nobody_spoke_in_has_nothing_behind_it(store):
    await _seeded(store)
    assert await _talker(store) == ""
    assert await store.read(ops.planes()) == [UI]


async def test_the_first_message_makes_the_plane_that_talks_and_starts_it(store):
    await _seeded(store)
    await _said(store, "how many planes are there")
    talker = await _talker(store)
    assert talker
    assert await store.read(ops.children(UI)) == [talker]
    assert await store.read(chat.drawn_of(talker)) == UI
    rows = {row["id"]: row for row in await store.read(ops.plane_rows())}
    assert rows[talker]["props"] == {
        "system": False,
        "ui": False,
        "made_by": "cc_chat",
        "backend": chat.TALKER_BACKEND,
    }
    assert rows[talker]["name"] == "ideas"
    assert await store.read(ops.cells(talker)) == [f"{talker}_{chat.CHAT_TALK}"]
    assert await store.read(ops.prog(chat.talk_of(talker))) == TALK
    # Up now, and back up whenever the space opens.
    assert talker in await store.read(init.booted())
    assert [run["by"] for run in await store.read(ops.runs(talker))] == [chat.BY]
    assert await _messages(store) == [{"role": chat.ROLE_USER, "text": "how many planes are there"}]


async def test_dropping_the_chat_drops_the_plane_that_talks(store):
    await _seeded(store)
    await _said(store, "hello")
    await store.run(ops.remove_plane(UI))
    assert await store.read(ops.planes()) == []


async def test_a_later_message_only_appends(store):
    """The pair and the start are the first message's alone. A second message
    makes no second Plane and asks for no second run."""
    await _seeded(store)
    await _said(store, "first")
    talker = await _talker(store)
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_AGENT, nu.Str("there are two")))
    await _said(store, "second")
    assert await _talker(store) == talker
    assert sorted(await store.read(ops.planes())) == sorted([UI, talker])
    assert len(await store.read(ops.runs(talker))) == 1
    assert [said["text"] for said in await _messages(store)] == [
        "first",
        "there are two",
        "second",
    ]


async def test_an_empty_submit_says_nothing_and_starts_nothing(store):
    await _seeded(store)
    await _said(store, "")
    assert await _talker(store) == ""
    # And no panel either, because a stray click is not a turn.
    assert await store.read(ops.cells(UI)) == []


async def test_a_submit_with_no_program_to_talk_with_starts_nothing(store):
    """The escape hatch submits with no program, because by then the chat
    has its Plane that talks. Before that, such a submit has nowhere to go."""
    await _seeded(store)
    await store.run(chat.submit(UI, nu.Str("hello")))
    assert await _talker(store) == ""
    assert await store.read(ops.cells(UI)) == []


async def test_a_submit_to_a_chat_nobody_made_makes_nothing(store):
    """A write under a missing key vivifies the row, so the submit is guarded on
    the Plane that draws: a chat dropped while a press was in flight must not
    grow back out of it."""
    await _said(store, "ghost", ui="p_nobody")
    assert await store.read(ops.planes()) == []


async def test_a_message_to_a_cell_nobody_made_makes_nothing(store):
    await _seeded(store)
    await _said(store, "hello")
    talker = await _talker(store)
    await store.run(chat.say("c_nobody", chat.ROLE_AGENT, nu.Str("ghost")))
    assert await store.read(ops.cells(talker)) == [f"{talker}_{chat.CHAT_TALK}"]
    assert "c_nobody" not in await store.read(nu.list(States.cells.keys()))


async def test_the_conversation_ships_as_values_not_views(store):
    """A list written into a kv leaf reads back as a live cursor into the
    store, which no frame can carry. Rebuilt, it is plain data."""
    await _seeded(store)
    await _said(store, "hello")
    said = await _messages(store)
    assert all(type(one) is dict for one in said)
    assert msgpack.packb(said) is not None


# --- what a submit puts up -------------------------------------------------------


async def test_a_submit_puts_the_panel_for_the_turn_up(store):
    """The whole reason the host appends this and the agent does not. A run
    takes as long as it takes, and the panel that says what it is doing has to
    be on the screen on the press, not after the first model call."""
    await _seeded(store)
    await _said(store, "what is here")
    assert await store.read(ops.cells(UI)) == [FIRST]
    rows = await store.read(ops.cell_rows(UI))
    assert rows[0]["name"] == f"{chat.CHAT_DISPLAY_NAME}1"
    assert rows[0]["prog"] == chat.DISPLAY_SOURCE


async def test_the_panel_the_running_turn_writes_into_is_the_one_just_made(store):
    """Read back rather than counted again. The op that made the Cell is the
    one that says which it is, or two callers have two answers."""
    await _seeded(store)
    await _said(store, "one")
    assert await store.read(chat.latest_display(chat.talk_of(await _talker(store)))) == FIRST


async def test_what_the_model_says_back_does_not_move_the_panel(store):
    """A turn is one input looped until done, however many passes it takes, so
    everything the agent says about it goes in the one panel."""
    await _seeded(store)
    await _said(store, "one")
    talker = await _talker(store)
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_AGENT, nu.Str("answered")))
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_SYSTEM, nu.Str("that run ended")))
    assert await store.read(chat.latest_display(chat.talk_of(talker))) == FIRST
    assert await store.read(ops.cells(UI)) == [FIRST]


async def test_a_second_turn_gets_a_panel_of_its_own(store):
    await _seeded(store)
    await _said(store, "one")
    await _said(store, "two")
    assert await store.read(ops.cells(UI)) == [FIRST, SECOND]
    assert await store.read(chat.latest_display(chat.talk_of(await _talker(store)))) == SECOND


@pytest.mark.parametrize(
    "source", [chat.DISPLAY_SOURCE, chat.OTHER_SOURCE], ids=["display", "other"]
)
async def test_the_cells_the_host_appends_load_the_way_the_kernel_loads_them(store, source):
    """Host owned, so nobody else is going to find out they do not build. Loaded
    with the rewrites a drawn Cell gets: rerooted, rooted under its browser
    session. Nothing brackets them: they bracket themselves."""
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    rewrite = Rewrites(Reroot("p", "c"), session_env("127.0.0.1:9")("s1").rewrite)
    prog = Space.cells["c"].prog
    term = await store.run(
        nustd.kv.Snapshot(
            prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )
    nu.validate(nu.compile(term))


# --- what a Cell asks when it comes up ---------------------------------------------


async def test_a_chat_nobody_started_is_owed_nothing(store):
    await _seeded(store)
    await _said(store, "one")
    talker = await _talker(store)
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_AGENT, nu.Str("answered")))
    assert await store.read(chat.unanswered(chat.talk_of("p_nobody"))) is False


async def test_a_message_the_cell_never_heard_is_still_answered(store):
    """The Cell comes up *because* of the first message, so it cannot have
    heard the change that carried it. This is what it asks instead."""
    await _seeded(store)
    await _said(store, "what is here")
    assert await store.read(chat.unanswered(chat.talk_of(await _talker(store)))) is True


async def test_a_reboot_does_not_replay_an_answered_conversation(store):
    """The failure this guards is a chat that re-answers its whole history
    every time the Space comes back up. Nothing is owed once the last word is
    the model's, however long the conversation is."""
    await _seeded(store)
    await _said(store, "one")
    talker = await _talker(store)
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_AGENT, nu.Str("answered one")))
    await _said(store, "two")
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_AGENT, nu.Str("answered two")))
    assert await store.read(chat.unanswered(chat.talk_of(talker))) is False


def test_a_fresh_subscription_every_time_and_two_containers_for_two_things():
    """A child scoped watch is silent in a worker, so the finest thing that can
    wake either of these is a container. They are two Cells: the conversation
    is the talking Cell's and a turn's trace is its panel's, which is what
    keeps the loop from waking once a pass on a row it does not read. Fresh
    nodes because a subscription is a handle and the first arm to end closes
    it under the other."""
    watch = chat.trace_changed(FIRST)
    assert repr(watch) == repr(ops.cell_state(FIRST, chat.Own.state).on_change())
    assert watch is not chat.trace_changed(FIRST)
    assert repr(watch) != repr(chat.changed(chat.talk_of("p_talker")))


def test_the_conversation_and_the_working_memory_are_two_containers():
    """A pass writes its working memory on every link, and the chat waits on
    the conversation. One container for both would wake the chat once a pass."""
    talked = repr(chat.changed(chat.talk_of("p_talker")))
    assert repr(session.changed(chat.talk_of("p_talker"))) != talked
    assert repr(chat.changed(chat.talk_of("p_talker"))) == talked


async def test_the_host_speaking_closes_an_unanswered_run(store):
    """A run that said nothing leaves the question standing, which would put
    the loop straight back round it. The host saying so is what ends that."""
    await _seeded(store)
    await _said(store, "do a thing")
    talker = await _talker(store)
    await store.run(chat.say(chat.talk_of(talker), chat.ROLE_SYSTEM, nu.Str("that run ended")))
    assert await store.read(chat.unanswered(chat.talk_of(talker))) is False


# --- what a turn draws -------------------------------------------------------------

#: A turn's program, as short as one can be. Nothing compiles it here: drawing
#: is a write, and a program that will not construct is a Cell that says so
#: when somebody runs it.
TURN = "def out():\n    return None\n"


async def test_a_turn_lands_as_a_cell_after_what_the_plane_already_holds(store):
    """The model answers by appending, so what the Plane holds keeps the place
    it was born in and turns pile up behind it."""
    await _seeded(store)
    await _said(store, "one")
    seeded = await store.read(ops.cells(UI))
    await store.run(chat.draw(UI, TURN, name="a table of planes"))
    drawn = await store.read(ops.cells(UI))
    assert drawn[: len(seeded)] == seeded
    assert len(drawn) == len(seeded) + 1
    row = (await store.read(ops.cell_rows(UI)))[-1]
    assert row["name"] == "a table of planes"
    assert "def out" in row["prog"]


async def test_two_turns_are_two_cells(store):
    """The id is minted per call, so the second turn appends rather than
    landing on top of the first."""
    await _seeded(store)
    await store.run(chat.draw(UI, TURN))
    await store.run(chat.draw(UI, TURN))
    assert len(await store.read(ops.cells(UI))) == 2


async def test_a_turn_drawn_on_a_plane_nobody_made_draws_nothing(store):
    """A write under a missing key vivifies the row, so a chat dropped mid turn
    would grow a Plane out of the answer arriving late."""
    await _seeded(store)
    await store.run(chat.draw("p_nobody", TURN))
    assert await store.read(ops.planes()) == [UI]


# --- what the agent is doing -------------------------------------------------------


async def _wrote(store, cycle, kind, text):
    """One state, into whichever panel the running turn is writing into."""
    panel = chat.latest_display(chat.talk_of(chat.talker_of(UI)))
    await store.run(chat.state(ops.snapshot(panel), cycle, kind, nu.Str(text)))


async def test_the_trace_reads_back_in_the_order_it_was_written(store):
    await _seeded(store)
    await _said(store, "what is here")
    await _wrote(store, chat.CYCLE_WORK, chat.KIND_HEARD, "what is here")
    await _wrote(store, chat.CYCLE_ANSWER, chat.KIND_DONE, "answer")
    assert await store.read(chat.trace_of(FIRST)) == [
        {"cycle": chat.CYCLE_WORK, "kind": chat.KIND_HEARD, "text": "what is here"},
        {"cycle": chat.CYCLE_ANSWER, "kind": chat.KIND_DONE, "text": "answer"},
    ]


async def test_a_note_is_the_one_row_the_model_writes(store):
    """Same list, same shape, one kind. What a program was for is known only to
    whoever wrote it, so this row is the model's and the host composes none."""
    await _seeded(store)
    await _said(store, "make me a table")
    await store.run(chat.note(FIRST, chat.CYCLE_WORK, nu.Str("drew the planes table")))
    assert await store.read(chat.trace_of(FIRST)) == [
        {"cycle": chat.CYCLE_WORK, "kind": chat.KIND_NOTE, "text": "drew the planes table"}
    ]


async def test_the_turn_you_scroll_back_to_still_holds_its_own_work(store):
    """The whole of why a trace is per panel. One list that every turn emptied
    could only ever show the turn you are standing in."""
    await _seeded(store)
    await _said(store, "one")
    await _wrote(store, chat.CYCLE_WORK, chat.KIND_RUNNING, "counted the planes")
    await _said(store, "two")
    await _wrote(store, chat.CYCLE_WORK, chat.KIND_RUNNING, "counted the cells")
    first = await store.read(chat.trace_of(FIRST))
    second = await store.read(chat.trace_of(SECOND))
    assert [row["text"] for row in first] == ["counted the planes"]
    assert [row["text"] for row in second] == ["counted the cells"]


async def test_a_turn_that_has_written_nothing_reads_empty(store):
    """Where a panel spends the first second of its life. The leaf is unwritten
    until the run says something, and an unwritten leaf reads EMPTY."""
    await _seeded(store)
    await _said(store, "one")
    assert await store.read(chat.trace_of(FIRST)) == []


async def test_a_panel_nobody_put_up_has_nothing_to_read(store):
    """A store key may not hold an empty segment, so the id ``latest_display``
    answers before the first submit is tested before anything takes it."""
    await _seeded(store)
    assert await store.read(chat.trace_of("")) == []
    await store.run(chat.state("", chat.CYCLE_WORK, chat.KIND_HEARD, nu.Str("into the void")))
    assert await store.read(ops.cells(UI)) == []


async def test_the_trace_ships_as_values_not_views(store):
    """Same failure as the conversation's, and this is the list that redraws on
    every write, so it is the one that would report itself loudest."""
    await _seeded(store)
    await _said(store, "one")
    await _wrote(store, chat.CYCLE_ANSWER, chat.KIND_DONE, "said it")
    rows = await store.read(chat.trace_of(FIRST))
    assert all(type(one) is dict for one in rows)
    assert msgpack.packb(rows) is not None


async def test_a_state_written_at_a_cell_nobody_made_makes_nothing(store):
    await _seeded(store)
    await _said(store, "one")
    await store.run(chat.state("c_nobody", chat.CYCLE_WORK, chat.KIND_DONE, nu.Str("ghost")))
    assert await store.read(ops.cells(UI)) == [FIRST]
    assert sorted(await store.read(ops.planes())) == sorted([UI, await _talker(store)])
    assert await store.read(States.cells.contains("c_nobody")) is False


# --- on real workers ---------------------------------------------------------------

#: A talking Cell with the model taken out of it. The loop around the answer
#: is the agent's, verbatim; only what it says is cheap, so this runs in
#: seconds and asks nothing of the network.
#:
#: The session write rides along because it is the one part of a run whose
#: address is built rather than declared bare, and the only thing that can
#: show it resolving in a worker through the proxied Navigator is a worker
#: doing it.
#:
#: Nothing is baked in: the panel it narrates into is read off its own
#: state, where the submit that made it wrote it.
ACK = """import nu
from nuspace import ops
from nuspace.agent import chat, session


def out():
    cell = ops.Here.cell

    def owed():
        return ops.snapshot(chat.unanswered(cell))

    def panel():
        return chat.latest_display(cell)

    # Bracketed by hand, as the agent is: each op commits on its own and reads
    # its arguments inside, the one bare write gets a commit of its own.
    ack = (
        session.cleared(cell)
        >> ops.atomic_state(session.session_of(cell).reply.set("acking"))
        >> chat.state(panel(), chat.CYCLE_WORK, chat.KIND_HEARD, "working")
        >> chat.say(cell, chat.ROLE_AGENT, "ack")
        >> chat.note(panel(), chat.CYCLE_ANSWER, "said it")
    )
    return nu.ForeverDo(
        nu.IfDo(owed(), ack) >> nu.WaitReactive(ops.snapshot(chat.changed(cell)), owed())
    )
"""


@pytest.fixture
async def space():
    k = await opened("nuspace-chat", spares=2)
    yield k
    await k.close()


async def test_a_started_chat_answers_every_message(space):
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
    """
    await space.run(ops.add_plane(UI, backend="async", ui=True, name="ideas"))
    await space.run(chat.submit(UI, nu.Str("one"), talk=ACK))
    talker = await space.read(chat.talker_of(UI))
    said = chat.messages_of(chat.talk_of(talker))
    await space.until(said, lambda rows: len(rows) == 2, SLOW)
    await space.run(chat.submit(UI, nu.Str("two"), talk=ACK))
    kept = await space.until(said, lambda rows: len(rows) == 4, SLOW)
    assert [one["text"] for one in kept] == ["one", "ack", "two", "ack"]
    assert await space.read(ops.cells(UI)) == [FIRST, SECOND]
    first = await space.read(chat.trace_of(FIRST))
    assert first == [
        {"cycle": chat.CYCLE_WORK, "kind": chat.KIND_HEARD, "text": "working"},
        {"cycle": chat.CYCLE_ANSWER, "kind": chat.KIND_NOTE, "text": "said it"},
    ]
    assert await space.read(chat.trace_of(SECOND)) == first
    assert await space.read(session.reply_of(chat.talk_of(talker))) == "acking"


#: A panel with the drawing taken out of it: it counts the rows it can see
#: instead of tiling them. What is left is the one thing a panel has to do that
#: no term on its own can show, which is hear a row that was written in another
#: process.
COUNTER = f'''import nu
import nustd.kv
import nuspace
from nuspace import ops
from nuspace.agent import chat


#: The panel this one is watching.
PANEL = "{FIRST}"


class Seen(nuspace.CellState):
    seen = nustd.kv.IntRef.slot()
    woke = nustd.kv.IntRef.slot()


def counted():
    return Seen.seen.set(nu.Len(nu.List(chat.trace_of(PANEL))))


def out():
    # Written on the way in, before anything is subscribed: a reader that
    # only ever writes from inside a reaction cannot tell a watch that is
    # dead from a turn that has said nothing yet. The count of wakes starts
    # at zero for the same reason. The helper brackets each step on its own.
    return ops.bracketed(
        counted()
        >> Seen.woke.set(0)
        >> nu.ReactForever(chat.trace_changed(PANEL), counted() >> Seen.woke.set(Seen.woke + 1))
    )
'''


class _Seen(CellState):
    """What the counter keeps, declared again here to read it from outside."""

    seen = nustd.kv.IntRef.slot()
    woke = nustd.kv.IntRef.slot()


async def test_a_panel_in_a_worker_hears_the_rows_a_turn_writes(space):
    """The other half of the live claim, and the half the panel is.

    A turn writes its trace from the process the agent runs in and the panel
    reads it from the process it is drawn in, so the subscription that keeps
    the panel live is proxied, and a proxied watch that does not carry is
    silent on both ends with nothing said anywhere. In process all of this
    passes whether or not it works.
    """
    await space.run(ops.add_plane(UI, backend="async", ui=True, name="ideas"))
    await space.run(chat.submit(UI, nu.Str("one"), talk=TALK))
    p, (c,) = await space.plane(COUNTER, backend="mp")
    await space.run(ops.plane_run(p, by="test"))
    seen = ops.cell_state(c, _Seen.seen)
    woke = ops.cell_state(c, _Seen.woke)
    # Up, and then long enough to subscribe: the count is written before
    # the watch binds. The rows go in after that, so what it ends up holding
    # is what the watch carried and not what it read on the way in.
    await space.until(woke.fallback(-1), lambda n: n == 0, SLOW)
    await asyncio.sleep(2.0)

    def wrote(text):
        return chat.state(FIRST, chat.CYCLE_WORK, chat.KIND_RUNNING, nu.Str(text))

    await space.run(wrote("counted the planes"))
    await space.until(seen.fallback(0), lambda n: n == 1, SLOW)
    await space.run(wrote("counted the cells"))
    await space.until(seen.fallback(0), lambda n: n == 2, SLOW)
    # More than once, which is the difference between a live panel and one
    # that shows the first row a turn wrote and nothing after it.
    assert await space.read(woke) >= 2
