"""Settings: the seed, and its cells loading through the kernel."""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.devices.web.sidebar import rows
from nuspace.system.kernel.body import Rewrites
from nuspace.system.ui import home, settings
from nuspace.system.ui.seed import seeded_id


async def test_settings_is_seeded_once_with_home_header(store):
    await store.run(home.ensure_home() >> settings.ensure_settings())
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == settings.PLANE]
    assert row["name"] == "Settings"
    assert row["props"] == {"system": True, "ui": True, "made_by": "", "backend": "async"}
    cells = await store.read(ops.cell_rows(settings.PLANE))
    assert [(c["name"], c["prog"]) for c in cells] == [("header", home.HEADER)]

    await store.run(ops.remove_cell(seeded_id(settings.PLANE, "header")))
    await store.run(settings.ensure_settings())
    cells = await store.read(ops.cell_rows(settings.PLANE))
    assert cells == []
    await store.run(ops.remove_plane(settings.PLANE))
    assert await store.read(ops.plane_exists(settings.PLANE))

    (space, *planes) = await store.read(rows())
    assert space["children"] == [home.PLANE, settings.PLANE]
    assert all(p["system"] for p in planes)


async def test_home_and_settings_are_not_pinned_when_seeded(store):
    await store.run(home.ensure_home() >> settings.ensure_settings())
    assert await store.read(ops.pinned()) == []


@pytest.mark.parametrize("cell", settings.CELLS, ids=lambda c: c[0])
async def test_each_cell_loads_through_the_kernel_rewrites(store, cell):
    _, source = cell
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite)
    prog = Space.cells["c"].prog
    term = await store.run(
        nustd.kv.Snapshot(
            prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite), scope=Space
        )
    )
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))
