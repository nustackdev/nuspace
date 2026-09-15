"""What a path is worth as columns, over a Shape built for the purpose.

The websocket test proves the loop; this proves the walk. ``Space`` only has
dicts of Shapes, so the sequence column, the mapping-of-values column, the
cap and the sentinels have nowhere to show themselves there.

Two runs over one rocksdb store, the way ``tests/nuspace/apps/conftest`` does
it: one to seed, one to read. Nothing here goes near a browser.
"""

from __future__ import annotations

import pytest

import nu
import nustd.kv
from nuspace.web.lens.reflect import column_terms


class Zoo(nu.Shape):
    """One of each kind of slot, which is the whole point of it."""

    title = nustd.kv.StrRef.slot()
    unset = nustd.kv.StrRef.slot()
    tags = nustd.kv.ListRef.slot(str)
    counts = nustd.kv.DictRef.slot(int)


@pytest.fixture
def zoo(tmp_path):
    """A store with one ``Zoo`` written into it, addressed by path."""
    path = tmp_path / "db"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


async def _seed(store):
    tree = nu.With(
        nustd.kv.rocksdb_navigator(store),
        body=nustd.kv.auto_flow_atomic(
            Zoo.title.set(nu.Str("a zoo"))
            >> Zoo.tags.init(nu.List.create())
            >> Zoo.tags.append(nu.Str("red"))
            >> Zoo.tags.append(nu.Str("blue"))
            >> Zoo.tags.append(nu.Str("green"))
            >> Zoo.counts.init(nu.Dict.create())
            >> Zoo.counts.set_item(nu.Str("red"), nu.Int(3))
            >> Zoo.counts.set_item(nu.Str("blue"), nu.Int(0)),
            scope=Zoo,
        ),
    )
    await nu.arun(tree, nu.Context())


async def _columns(store, path, max_rows=200):
    tree = nu.With(
        nustd.kv.rocksdb_navigator(store, read_only=True),
        body=nustd.kv.auto_flow_atomic(column_terms(Zoo, path, max_rows), scope=Zoo),
    )
    cols, _ = await nu.arun(tree, nu.Context())
    return cols


@pytest.mark.timeout(60)
async def test_the_root_column_is_the_shape_and_its_leaf_values(zoo):
    """Slots are schema; a leaf slot also carries what the store has."""
    await _seed(zoo)
    (root,) = await _columns(zoo, ())
    assert root["kind"] == "shape"
    assert root["total"] == 4
    rows = {e["key"]: e for e in root["entries"]}
    assert [e["kind"] for e in root["entries"]] == ["leaf", "leaf", "sequence", "mapping"]
    assert rows["title"]["preview"] == "a zoo"
    assert rows["title"]["vtype"] == "str"
    # A slot nobody ever wrote reads as the sentinel it is, not as "".
    assert rows["unset"]["vtype"] == "empty"
    assert rows["unset"]["preview"] == ""
    # A structured slot is a door. It says which kind of column it opens and
    # touches the store for nothing.
    assert rows["tags"]["preview"] == ""
    assert all(e["navigable"] for e in root["entries"])


@pytest.mark.timeout(60)
async def test_a_sequence_column_is_positions_and_values(zoo):
    await _seed(zoo)
    cols = await _columns(zoo, ("tags",))
    assert len(cols) == 2
    col = cols[1]
    assert col["kind"] == "sequence"
    assert col["total"] == 3
    assert [e["key"] for e in col["entries"]] == ["0", "1", "2"]
    assert [e["preview"] for e in col["entries"]] == ["red", "blue", "green"]
    # A position holds a value, and there is nothing under it to open.
    assert not any(e["navigable"] for e in col["entries"])


@pytest.mark.timeout(60)
async def test_a_mapping_of_values_shows_the_values(zoo):
    """A dict of ints is not a dict of Shapes, and the column says so."""
    await _seed(zoo)
    cols = await _columns(zoo, ("counts",))
    col = cols[1]
    assert col["kind"] == "mapping"
    assert col["total"] == 2
    rows = {e["key"]: e for e in col["entries"]}
    assert rows["red"]["preview"] == "3"
    assert rows["red"]["vtype"] == "int"
    # Zero is a value. It must not read as empty, or every falsy leaf in the
    # store would look unwritten.
    assert rows["blue"]["preview"] == "0"
    assert rows["blue"]["vtype"] == "int"


@pytest.mark.timeout(60)
async def test_a_leaf_column_carries_the_whole_value(zoo):
    await _seed(zoo)
    cols = await _columns(zoo, ("title",))
    assert len(cols) == 2
    (cell,) = cols[1]["entries"]
    assert cols[1]["kind"] == "leaf"
    assert cell["text"] == "a zoo"
    assert cell["clipped"] is False
    assert cell["navigable"] is False


@pytest.mark.timeout(60)
async def test_the_cap_clips_the_rows_and_keeps_the_total(zoo):
    """``max_rows`` is a hard cap with no pagination, and the total says so."""
    await _seed(zoo)
    for path in (("tags",), ("counts",)):
        col = (await _columns(zoo, path, max_rows=1))[1]
        assert len(col["entries"]) == 1
        assert col["total"] > 1


@pytest.mark.timeout(60)
async def test_a_segment_that_names_nothing_is_one_error_column(zoo):
    """Total by construction: a bad crumb costs its own column and no more."""
    await _seed(zoo)
    cols = await _columns(zoo, ("title", "nope"))
    assert len(cols) == 3
    assert cols[0]["kind"] == "shape"
    assert cols[2]["entries"][0]["vtype"] == "error"


@pytest.mark.timeout(60)
async def test_a_read_that_fails_at_run_still_answers_with_a_cascade(zoo):
    """A frame always comes back, or the browser waits on one forever.

    Indexing a list by a name gets past the walk and dies in the read, which
    is the failure the construction-time guard cannot see.
    """
    from nuspace.web.lens.reflect import columns

    await _seed(zoo)
    tree = nu.With(
        nustd.kv.rocksdb_navigator(zoo, read_only=True),
        body=nustd.kv.auto_flow_atomic(
            columns(Zoo, nu.List.of(nu.Str("tags"), nu.Str("red"))), scope=Zoo
        ),
    )
    cols, _ = await nu.arun(tree, nu.Context())
    assert cols[-1]["entries"][0]["vtype"] == "error"
