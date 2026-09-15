"""nuspace.apps: every app in the space, running, as one Nu tree.

The whole lifecycle in one run, driven entirely from the tree: two apps are
written and launched, one snippet is edited and only that app restarts, one
app is deleted and only its worker dies. Watch the worker ids -- pool ids are
never reused, so a changed id means that app restarted.

    1. two apps written    -> the live loop launches both
    2. counter edited      -> only the counter restarts
    3. mirror deleted      -> only the mirror's worker dies

A snippet owns its own atomicity: the runner brackets its own read of the
snippet and stops, so every kv write below is wrapped by the snippet making
it. Drop the wrap and the app dies with LookupError: No binding for
SnapshotProtocol.

Run me: uv run python examples/apps.py
"""

import asyncio
import shutil
import sys
from pathlib import Path

import nu
from nu.core.io import STDOUT
from nuspace.apps import Runner, ops, run_apps
from nuspace.core.shapes import Space


ROOT = Path("/tmp/nuspace-apps-demo")  # noqa: S108

# A counter. Ticks its own row every 0.1s, stepping by `step`, forever. An app
# gets the same scope a section does, and `section` is its own id: an app is a
# section with no page. Editing `step` is what the demo edits.
COUNTER = '''import nu
import nustd.kv
from nuspace.core.shapes import Space


def out(section):
    """Tick a counter in this app's own corner of the space's scratch kv."""
    data = Space.state[section].data
    now = nu.ToInt(data.get_item("ticks", nu.Str("0")))
    tick = data.set_item("ticks", nu.ToStr(now + nu.Int({step})))
    return nustd.kv.auto_flow_atomic(
        data.set_item("ticks", nu.Str("0")) >> nu.ForeverDo(nu.DelayedDo(0.1, tick)),
        scope=Space,
    )
'''

# Reads another app's counter and copies it into its own row. Two apps, two
# processes, both reaching the one store through their own proxy, and the app
# being watched is named by id rather than by a path formatted into the source.
MIRROR = '''import nu
import nustd.kv
from nuspace.core.shapes import Space

WATCHED = "a_counter"


def out(section):
    """Copy another app's tick count into this one's row."""
    mine = Space.state[section].data
    theirs = Space.state[WATCHED].data
    copy = mine.set_item("seen", nu.ToStr(theirs.get_item("ticks", nu.Str("0"))))
    return nustd.kv.auto_flow_atomic(nu.ForeverDo(nu.DelayedDo(0.1, copy)), scope=Space)
'''


def report(label):
    """What the runner and the apps have to say for themselves, right now."""
    return nu.Print(
        STDOUT,
        label,
        "\n  workers:",
        Runner.workers,
        "\n  counter:",
        nu.dict(Space.state["a_counter"].data.items()),
        "\n  mirror: ",
        nu.dict(Space.state["a_mirror"].data.items()),
    )


# The demo, as one tree, running beside the live loop after the seed pass.
#
# The waits are generous on purpose: the subscription is depth-unbounded, so
# writing an app's three fields costs three reconciles, each a kill + spawn +
# dispatch. That churn is why the worker ids below are not 0 and 1.
SCRIPT = (
    nu.DelayedDo(0.2, ops.add_app(COUNTER.format(step=1), app_id="a_counter"))
    >> nu.DelayedDo(0.2, ops.add_app(MIRROR, app_id="a_mirror"))
    >> nu.DelayedDo(4.0, report("\n[1] both apps up and running"))
    # Edit one snippet. Only the counter restarts: its worker id moves, the
    # mirror's does not, and the counter starts over from zero stepping by
    # ten.
    >> nu.DelayedDo(0.2, ops.set_snippet("a_counter", COUNTER.format(step=10)))
    >> nu.DelayedDo(2.0, report("\n[2] counter edited, mirror untouched"))
    # Delete one app. Its worker is killed and forgotten; the counter keeps
    # ticking and the mirror's value simply stops moving.
    >> nu.DelayedDo(0.2, ops.remove_app("a_mirror"))
    >> nu.DelayedDo(2.0, report("\n[3] mirror deleted, counter undisturbed"))
)


def demo():
    shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_apps(str(ROOT / "db"), alongside=SCRIPT, duration=12.0))


if __name__ == "__main__":
    sys.exit(demo())
