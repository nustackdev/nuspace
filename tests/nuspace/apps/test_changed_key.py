"""What the apps subscription actually delivers, pinned.

``CHANGED_APP_INDEX`` is a measurement, not a guess: these tests record the
real keys the observer hands ``ReactForever`` and assert the app id is where
the runner slices for it. If the key shape ever changes, this fails loudly
instead of the runner silently reconciling the wrong app.
"""

from __future__ import annotations

from ast import literal_eval

import pytest

import nu
import nu.kv
from nuspace.apps import CHANGED_APP_INDEX, ops
from nuspace.core.shapes import Space

from .conftest import PROBE, read_probes, seq, write_app


pytestmark = pytest.mark.timeout(120)


def _record():
    """Append every key the subscription delivers into the probe row."""
    key = nu.TupleAttrRef("k")
    keys = Space.state[PROBE].data
    return nu.ReactForever(
        Space.apps.on_change(),
        keys.set_item(nu.Str("key.") + nu.ToStr(nu.Len(keys)), nu.ToStr(key)),
        changed_key="k",
    )


async def _keys(path, script):
    """Run ``script`` beside a recorder and give back the keys it saw, in order."""
    tree = nu.With(
        nu.kv.rocksdb_navigator(path),
        body=nu.kv.auto_flow_atomic(
            Space.apps.init(nu.Dict.create())
            # The recorder counts what it has written, so the row it counts
            # has to be there before the first key lands.
            >> Space.state[PROBE].data.init(nu.Dict.create())
            >> nu.Race(_record() | script, nu.DelayedDo(nu.Float(3.0), nu.Noop())),
            scope=Space,
        ),
    )
    await nu.arun(tree, nu.Context(), max_parallel=16)
    recorded = await read_probes(path)
    return [literal_eval(v) for k, v in sorted(recorded.items()) if k.startswith("key.")]


async def test_the_app_id_sits_at_the_pinned_index(store):
    """Add, edit and delete, and read the app id out of every key at index 2."""
    script = (
        nu.DelayedDo(0.2, write_app("a_one"))
        >> nu.DelayedDo(0.2, write_app("a_two"))
        >> nu.DelayedDo(0.2, ops.set_snippet("a_one", "edited"))
        >> nu.DelayedDo(0.2, ops.remove_app("a_two"))
    )
    keys = await _keys(store, script)

    assert keys, "the subscription delivered nothing at all"
    assert CHANGED_APP_INDEX == 2
    # Absolute keys are rooted, so every key starts the same way.
    assert {tuple(k[:2]) for k in keys} == {("/", "apps")}
    # Every key long enough to name an app names one of ours, at that index.
    named = [k[CHANGED_APP_INDEX] for k in keys if len(k) > CHANGED_APP_INDEX]
    assert set(named) == {"a_one", "a_two"}
    # Both row-level and field-level keys occur, and the index works for both.
    assert any(len(k) == CHANGED_APP_INDEX + 1 for k in keys)
    assert any(len(k) > CHANGED_APP_INDEX + 1 for k in keys)


async def test_a_bare_container_key_occurs_and_names_no_app(store):
    """The dict itself changing is reported too, with nothing at the index.

    This is why the live loop guards on length: slicing this one would raise
    IndexError inside the react loop and leave the runner deaf.
    """
    keys = await _keys(store, nu.DelayedDo(0.2, seq(write_app("a_one"))))

    assert any(len(k) <= CHANGED_APP_INDEX for k in keys)
