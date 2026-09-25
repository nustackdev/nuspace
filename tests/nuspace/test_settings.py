"""Settings: the seed, the telemetry ops, and the telemetry cell drawn once."""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system import home, settings
from nuspace.system.devices.web.env import session_env
from nuspace.system.devices.web.sidebar import rows
from nuspace.system.kernel.body import Bracketed, Rewrites
from nustd.ui import Session


async def test_settings_is_seeded_once_with_home_header(store):
    await store.run(home.ensure_home() >> settings.ensure_settings())
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == settings.PLANE]
    assert row["name"] == "Settings"
    assert row["props"] == {"system": True, "ui": True, "made_by": ""}
    cells = await store.read(ops.cell_rows(settings.PLANE))
    assert [(c["id"], c["prog"]) for c in cells] == [
        ("header", home.HEADER),
        ("telemetry", settings.TELEMETRY),
    ]

    await store.run(ops.remove_cell(settings.PLANE, "header"))
    await store.run(settings.ensure_settings())
    cells = await store.read(ops.cell_rows(settings.PLANE))
    assert [c["id"] for c in cells] == ["telemetry"]
    assert await store.run(ops.remove_plane(settings.PLANE)) is False

    (space, *planes) = await store.read(rows())
    assert space["children"] == [home.PLANE, settings.PLANE]
    assert all(p["system"] for p in planes)


async def test_home_and_settings_are_pinned_on_first_seed_only(store):
    await store.run(home.ensure_home() >> settings.ensure_settings())
    assert await store.read(ops.pinned()) == [home.PLANE, settings.PLANE]
    # Unpinned by the owner: seeding again leaves it that way.
    await store.run(ops.unpin_plane(settings.PLANE) >> ops.move_pin(home.PLANE, 0))
    await store.run(home.ensure_home() >> settings.ensure_settings())
    assert await store.read(ops.pinned()) == [home.PLANE]


async def test_telemetry_is_off_until_set(store):
    assert await store.read(nustd.kv.Snapshot(ops.telemetry(), scope=Space)) is False
    await store.run(ops.set_telemetry(True))
    assert await store.read(Space.settings.telemetry) is True
    await store.run(ops.set_telemetry(False))
    assert await store.read(nustd.kv.Snapshot(ops.telemetry(), scope=Space)) is False


@pytest.mark.parametrize("cell", settings.CELLS, ids=lambda c: c[0])
async def test_each_cell_loads_through_the_kernel_rewrites(store, cell):
    _, source = cell
    await store.run(ops.add_plane("p") >> ops.add_cell("p", source, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite, Bracketed())
    prog = Space.planes["p"].cells["c"].prog
    term = await store.run(
        nustd.kv.auto_flow_atomic(
            prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


async def _drawn(store) -> list:
    namespace: dict = {}
    exec(compile(settings.TELEMETRY, "cell", "exec"), namespace)  # noqa: S102
    session = _Recording()
    await nu.arun(namespace["draw"](), store.ctx.bind(Session, session))
    return [(frame.ref, frame.payload) for frame in session.frames]


async def test_telemetry_switch_draws_the_stored_setting(store):
    assert await _drawn(store) == [(("telemetry", "on"), False)]
    await store.run(ops.set_telemetry(True))
    assert await _drawn(store) == [(("telemetry", "on"), True)]
