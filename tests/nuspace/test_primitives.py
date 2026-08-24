"""Kv-level tests for nuspace primitives.

Boot a rocksdb-backed Nu tree, run the primitives, snapshot the kv, assert
the resulting layout. In-memory would be ideal but the mvp targets rocksdb
end-to-end; using tmp_path is cheap.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import nu
import pytest

from nuspace.core.primitives import AddBlock, AddPage, RemoveBlock, RemovePage
from nuspace.core.shapes import ACTIVE_PAGE, Space


@pytest.mark.asyncio
async def test_add_page_add_block_kv_layout():
    d = Path(tempfile.mkdtemp())
    boot = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.auto_flow_atomic(
            AddPage("home", "Home")
            >> AddBlock("home", "text", "SNIP", "hi", app_id="b_xyz")
            >> ACTIVE_PAGE.set("home"),
        ),
    )
    await nu.arun(boot)

    async def snap(ref, list_of=False):
        r = nu.kv.Snapshot(nu.Collect(nu.Iter(ref))) if list_of else nu.kv.Snapshot(ref)
        v, _ = await nu.arun(nu.With(nu.kv.rocksdb_navigator(str(d)), body=r))
        return list(v) if list_of else v

    assert list(await snap(Space.pages_index, list_of=True)) == ["home"]
    assert str(await snap(Space.pages["home"].title)) == "Home"
    assert list(await snap(Space.pages["home"].blocks, list_of=True)) == ["b_xyz"]
    assert str(await snap(Space.apps["b_xyz"].kind)) == "text"
    assert str(await snap(Space.apps["b_xyz"].snippet)) == "SNIP"
    assert str(await snap(Space.apps["b_xyz"].value)) == "hi"
    assert str(await snap(ACTIVE_PAGE)) == "home"


@pytest.mark.asyncio
async def test_remove_block_unlinks_and_deletes():
    d = Path(tempfile.mkdtemp())
    setup = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.auto_flow_atomic(
            AddPage("p", "P")
            >> AddBlock("p", "text", "S", "", app_id="b_1")
            >> AddBlock("p", "text", "S", "", app_id="b_2"),
        ),
    )
    await nu.arun(setup)
    remove = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.auto_flow_atomic(RemoveBlock("p", "b_1")),
    )
    await nu.arun(remove)

    app = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.Snapshot(nu.Collect(nu.Iter(Space.pages["p"].blocks))),
    )
    v, _ = await nu.arun(app)
    assert list(v) == ["b_2"]


@pytest.mark.asyncio
async def test_remove_page_unlinks_index():
    d = Path(tempfile.mkdtemp())
    setup = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.auto_flow_atomic(
            AddPage("home", "Home") >> AddPage("notes", "Notes"),
        ),
    )
    await nu.arun(setup)
    rm = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.auto_flow_atomic(RemovePage("home")),
    )
    await nu.arun(rm)
    app = nu.With(
        nu.kv.rocksdb_navigator(str(d)),
        body=nu.kv.Snapshot(nu.Collect(nu.Iter(Space.pages_index))),
    )
    v, _ = await nu.arun(app)
    assert list(v) == ["notes"]
