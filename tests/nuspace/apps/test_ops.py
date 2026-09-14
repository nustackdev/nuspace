"""Every apps primitive, against a real on-disk RocksDB.

No workers and no runner here: an op is a tree, so the whole test is "run the
tree, read the store back". Only ``running`` / ``is_running`` need a host
context instead of a store, because ``Runner.workers`` is mem.
"""

from __future__ import annotations

import nu
import nu.kv
from nuspace.apps import Runner, ops
from nuspace.core.shapes import Space


SRC = "def out():\n    return None\n"


async def do(path, term):
    """Run one term against the store and give back what it evaluated to."""
    tree = nu.With(
        nu.kv.rocksdb_navigator(path),
        body=nu.kv.auto_flow_atomic(term, scope=Space),
    )
    value, _ = await nu.arun(tree, nu.Context())
    return value


async def in_host(data, term):
    """Run one term over ``data``, the dict substrate ``nu.mem`` lives in.

    Passing the same dict twice is how a read sees what an earlier write did:
    mem keeps nothing of its own between runs.
    """
    # Bound on the Context, not with Provide: Provide's second argument is the
    # kwargs to construct with, so it would hand every run a fresh empty dict.
    value, _ = await nu.arun(term, nu.Context().bind(dict, data))
    return value


async def test_add_app_writes_every_field(store):
    await do(store, ops.add_app(SRC, app_id="a_one", name="One", policy="manual"))

    assert await do(store, ops.snippet_of("a_one")) == SRC
    assert await do(store, Space.apps["a_one"].name) == "One"
    assert await do(store, Space.apps["a_one"].policy) == "manual"


async def test_add_app_defaults_the_name_to_the_id_and_the_policy_to_always(store):
    await do(store, ops.add_app(SRC, app_id="a_one"))

    assert await do(store, Space.apps["a_one"].name) == "a_one"
    assert await do(store, Space.apps["a_one"].policy) == "always"


async def test_add_app_with_no_id_mints_an_ordered_one(store):
    await do(store, ops.add_app(SRC))
    await do(store, ops.add_app(SRC))

    ids = await do(store, ops.app_ids())
    assert len(ids) == 2
    assert all(i.startswith("a_") for i in ids)
    # Minted in creation order, and the store lists them sorted by key.
    assert ids == sorted(ids)


async def test_set_snippet_replaces_the_source(store):
    await do(store, ops.add_app(SRC, app_id="a_one"))
    await do(store, ops.set_snippet("a_one", "edited"))

    assert await do(store, ops.snippet_of("a_one")) == "edited"


async def test_rename_app_moves_the_name_and_not_the_id(store):
    await do(store, ops.add_app(SRC, app_id="a_one"))
    await do(store, ops.rename_app("a_one", "Renamed"))

    assert await do(store, Space.apps["a_one"].name) == "Renamed"
    assert await do(store, ops.app_ids()) == ["a_one"]


async def test_set_policy_replaces_the_policy(store):
    await do(store, ops.add_app(SRC, app_id="a_one"))
    await do(store, ops.set_policy("a_one", "manual"))

    assert await do(store, Space.apps["a_one"].policy) == "manual"


async def test_remove_app_drops_the_row_and_leaves_the_others(store):
    await do(store, ops.add_app(SRC, app_id="a_one") >> ops.add_app(SRC, app_id="a_two"))
    await do(store, ops.remove_app("a_one"))

    assert await do(store, ops.app_ids()) == ["a_two"]
    assert await do(store, ops.exists("a_one")) is False


async def test_remove_app_on_a_missing_app_is_harmless(store):
    await do(store, ops.add_app(SRC, app_id="a_one"))
    await do(store, ops.remove_app("a_nope"))

    assert await do(store, ops.app_ids()) == ["a_one"]


async def test_app_ids_and_exists_answer_for_an_empty_space(store):
    await do(store, Space.apps.init(nu.Dict.create()))

    assert await do(store, ops.app_ids()) == []
    assert await do(store, ops.exists("a_one")) is False


async def test_error_of_reads_what_the_runner_recorded(store):
    await do(store, Space.state["a_one"].error.set(nu.Str("boom")))

    assert await do(store, ops.error_of("a_one")) == "boom"
    # Total on purpose: an app that constructed fine has no error at all.
    assert await do(store, ops.error_of("a_two")) == ""


async def test_running_and_is_running_read_the_host_bookkeeping():
    data = {}
    await in_host(
        data, Runner.workers.init(nu.Dict.create()) >> Runner.workers.set_item("a_one", nu.Int(7))
    )

    assert await in_host(data, ops.running()) == {"a_one": 7}
    assert await in_host(data, ops.is_running("a_one")) is True
    assert await in_host(data, ops.is_running("a_two")) is False


async def test_init_apps_creates_the_container_and_is_idempotent(store):
    await do(store, ops.init_apps())
    await do(store, ops.add_app(SRC, app_id="a_one"))
    await do(store, ops.init_apps())

    assert await do(store, ops.app_ids()) == ["a_one"]


async def test_clear_error_forgets_what_the_runner_recorded(store):
    await do(store, Space.state["a_one"].error.set(nu.Str("boom")))
    await do(store, ops.clear_error("a_one"))

    assert await do(store, ops.error_of("a_one")) == ""
    # An app that never failed has no error, and dropping it is still a no-op.
    await do(store, ops.clear_error("a_two"))


async def test_app_rows_answers_with_one_dict_per_app_in_mint_order(store):
    await do(
        store,
        ops.add_app(SRC, app_id="a_one", name="One")
        >> ops.add_app("other", app_id="a_two", name="Two", policy="manual"),
    )

    assert await do(store, ops.app_rows()) == [
        {"id": "a_one", "name": "One", "source": SRC, "policy": "always"},
        {"id": "a_two", "name": "Two", "source": "other", "policy": "manual"},
    ]


async def test_app_statuses_read_failed_off_the_error_key_and_idle_otherwise(store):
    await do(store, ops.add_app(SRC, app_id="a_one") >> ops.add_app(SRC, app_id="a_two"))
    await do(store, Space.state["a_two"].error.set(nu.Str("boom")))

    assert await do(store, ops.app_statuses()) == [
        {"section_id": "a_one", "state": "idle", "error": "", "started_at": 0},
        {"section_id": "a_two", "state": "failed", "error": "boom", "started_at": 0},
    ]


async def test_app_statuses_read_running_only_when_supervised(store):
    """Unsupervised never claims an app is running, because nothing would be."""
    await do(store, ops.add_app(SRC, app_id="a_one") >> ops.init_apps())
    data = {}
    await in_host(data, Runner.workers.init(nu.Dict.create()))
    await in_host(data, Runner.workers.set_item("a_one", nu.Int(7)))

    tree = nu.With(
        nu.kv.rocksdb_navigator(store),
        body=nu.kv.auto_flow_atomic(ops.app_statuses(supervised=True), scope=Space),
    )
    supervised, _ = await nu.arun(tree, nu.Context().bind(dict, data))

    assert [r["state"] for r in supervised] == ["running"]
    assert [r["state"] for r in await do(store, ops.app_statuses())] == ["idle"]
