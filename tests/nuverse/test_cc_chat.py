"""The ``cc_chat`` Plane: what creating it seeds, and what its first message makes.

The agent itself is ``tests/nuspace/test_agent.py``. What is left here is the
part the Plane decides: its one Cell, the talking Cell it hands the first
message, and that a chat's Plane that talks is not mistaken for a job.
"""

from __future__ import annotations

import nu
import nu.prog
import nustd.kv
from nuspace import ops
from nuspace.agent import chat
from nuspace.shapes import Reroot, Space, reroot
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui import Session
from nuverse.planes import cc_chat, jobs


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


def _cell(source: str) -> dict:
    """A cell's module namespace, its names reachable from here."""
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    return namespace


async def _loaded(store, source: str, *, drawn: bool) -> nu.Nu:
    """``source`` loaded the way the kernel loads a Cell: rerooted, and nothing bracketed for it."""
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    steps = [Reroot("p", "c")]
    if drawn:
        steps.append(session_env("127.0.0.1:9")("s1").rewrite)
    rewrite = Rewrites(*steps)
    prog = Space.cells["c"].prog
    return await store.run(
        nustd.kv.Snapshot(
            prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )


def test_the_plane_registers_last_and_is_named_after_its_backend():
    from nuverse.planes import PLANES

    assert PLANES[-1] is cc_chat.PLANE
    assert (cc_chat.PLANE.name, cc_chat.PLANE.label) == ("cc_chat", "CC chat")


async def test_creating_a_chat_seeds_one_read_only_plane_with_its_box(store):
    await store.run(ops.create_plane(cc_chat.PLANE, name="ideas", plane_id="p1"))
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == "p1"]
    assert row["props"] == {"system": False, "ui": True, "made_by": "cc_chat", "backend": "async"}
    assert row["meta"]["editable"] is False
    cells = await store.read(ops.cell_rows("p1"))
    assert [(c["name"], c["prog"]) for c in cells] == [("input", cc_chat.INPUT)]
    # Nothing talks until somebody does.
    assert await store.read(chat.talker_of("p1")) == ""


def test_the_input_cell_carries_the_talking_cell_verbatim():
    assert _cell(cc_chat.INPUT)["TALK"] == cc_chat.TALK


async def test_the_input_cell_loads_through_the_kernel_rewrites(store):
    term = await _loaded(store, cc_chat.INPUT, drawn=True)
    nu.validate(nu.compile(term))


def test_the_talking_cell_constructs_and_validates():
    term = nu.run(nu.prog.LoadNu(cc_chat.TALK))[0]
    nu.validate(nu.compile(term))


async def test_the_talking_cell_loads_through_the_kernel_rewrites(store):
    term = await _loaded(store, cc_chat.TALK, drawn=False)
    nu.validate(nu.compile(term))


async def test_the_first_message_from_the_box_makes_the_plane_that_talks(store):
    await store.run(ops.create_plane(cc_chat.PLANE, name="ideas", plane_id="p1"))
    talk = _cell(cc_chat.INPUT)["TALK"]
    await store.run(chat.submit("p1", nu.Str("hello"), talk=talk))
    talker = await store.read(chat.talker_of("p1"))
    assert await store.read(ops.children("p1")) == [talker]
    assert await store.read(ops.prog(chat.talk_of(talker))) == cc_chat.TALK
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == talker]
    assert row["props"]["made_by"] == "cc_chat"


async def test_a_chat_is_not_a_job(store):
    """The Plane a chat talks through is headless like a job, and made by the
    chat, so the Jobs table leaves it to the chat."""
    await store.run(ops.create_plane(cc_chat.PLANE, name="ideas", plane_id="p1"))
    await store.run(chat.submit("p1", nu.Str("hello"), talk=cc_chat.TALK))
    await store.run(ops.add_plane("j1", name="Nightly", backend="mp", made_by="jobs"))
    session = _Recording()
    draw = nu.Frame(ops.Here, reroot(_cell(jobs.TABLE)["draw"](), "jp", "jobs"), plane="jp")
    await nu.arun(draw, store.ctx.bind(Session, session))
    (table,) = [frame.payload for frame in session.frames]
    assert [row[1] for row in table["rows"]] == ["j1"]
