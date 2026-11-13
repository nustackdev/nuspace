"""A pane's scroll, driven from a cell: ``nuspace.web.pane()`` and its writes.

What a cell builds is checked over a fake session, the way a cell run sends
it: :class:`Here` bound, the session env's rewrite applied. Each write must
land on this plane's pane node, ``viewer/panes/<plane>``, never under the
cell, tagged the way the browser's pane handler reads it
(``pkgs/ts/nuspace-ui/src/pane/scroll.ts``).
"""

from __future__ import annotations

import asyncio

import pytest

import nu
import nuspace.web as web
from nuspace.places import Here, inside
from nuspace.web.shell import Shell
from nuspace.web.utils import CellRoot
from nuspace.web.viewer import PaneRef
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.session import Session


class FakeSession(WsSession):
    """A session with no socket: the frames sent are kept."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)


async def _sent(term: nu.Nu, *, plane: str = "p1", cell: str = "c1") -> list[Frame]:
    """``term`` run as a cell run on a tab runs it: inside Here, rerooted, on a session."""
    session = FakeSession()
    body = inside(CellRoot(Shell.viewer, Here.cell)(term), plane=plane, cell=cell)
    await nu.arun(body, nu.Context().bind(Session, session))
    return session.frames


def test_pane_is_the_running_cells_pane_ref():
    assert isinstance(web.pane(), PaneRef)


async def test_follow_writes_on_this_planes_pane():
    (frame,) = await _sent(web.pane().follow("bottom"), plane="p7")
    assert tuple(frame.ref) == ("viewer", "panes", "p7")
    assert frame.payload == {"op": "set_follow", "follow": "bottom"}
    (frame,) = await _sent(web.pane().follow("none"))
    assert frame.payload == {"op": "set_follow", "follow": "none"}


async def test_follow_defaults_to_bottom():
    (frame,) = await _sent(web.pane().follow())
    assert frame.payload["follow"] == "bottom"


async def test_scroll_is_one_shot_with_a_fresh_seq_per_run():
    once = web.pane().scroll("top", smooth=True)
    (first,) = await _sent(once)
    (second,) = await _sent(once)
    assert tuple(first.ref) == ("viewer", "panes", "p1")
    assert {k: v for k, v in first.payload.items() if k != "seq"} == {
        "op": "scroll",
        "to": "top",
        "cell_id": "",
        "smooth": True,
    }
    assert isinstance(first.payload["seq"], str) and first.payload["seq"]
    assert first.payload["seq"] != second.payload["seq"]


async def test_scroll_twice_in_one_run_sends_two_seqs():
    frames = await _sent(web.pane().scroll() >> web.pane().scroll())
    assert [f.payload["to"] for f in frames] == ["bottom", "bottom"]
    assert frames[0].payload["seq"] != frames[1].payload["seq"]


async def test_scroll_to_a_cell():
    (frame,) = await _sent(web.pane().scroll_to(Here.cell), cell="c9")
    assert tuple(frame.ref) == ("viewer", "panes", "p1")
    assert frame.payload["to"] == "cell"
    assert frame.payload["cell_id"] == "c9"
    assert frame.payload["smooth"] is False


def test_a_bad_mode_or_place_refuses_at_build():
    with pytest.raises(ValueError, match="follow"):
        web.pane().follow("top")
    with pytest.raises(ValueError, match="scroll_to"):
        web.pane().scroll("cell")


async def test_outside_a_cell_run_there_is_no_pane():
    with pytest.raises(LookupError):
        await nu.arun(web.pane().follow(), nu.Context().bind(Session, FakeSession()))


async def test_the_tail_example_follows_and_appends():
    """The testing extension's ``tail`` cell: follow on, then a line a second."""
    from _support.specs import TAIL_SRC

    program: dict = {}
    exec(TAIL_SRC, program)  # noqa: S102
    session = FakeSession()
    body = inside(CellRoot(Shell.viewer, Here.cell)(program["out"]()), plane="p1", cell="c1")
    task = asyncio.create_task(nu.arun(body, nu.Context().bind(Session, session)))
    try:
        deadline = asyncio.get_running_loop().time() + 3.0
        while len(session.frames) < 3:
            assert asyncio.get_running_loop().time() < deadline, "timed out"
            await asyncio.sleep(0.01)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    cleared, follow, line = session.frames[:3]
    assert tuple(cleared.ref) == ("viewer", "cells", "c1", "lines")
    assert tuple(follow.ref) == ("viewer", "panes", "p1")
    assert follow.payload == {"op": "set_follow", "follow": "bottom"}
    assert (line.op, line.payload) == ("append", "line 1")
