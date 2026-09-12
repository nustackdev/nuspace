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
from nuspace.apps import Runner, run_apps
from nuspace.core.shapes import Space


ROOT = Path("/tmp/nuspace-apps-demo")  # noqa: S108

# A counter. Writes apps.<id>.ticks every 0.1s, stepping by `step`, forever.
# Editing `step` in the stored source is what the demo edits.
COUNTER = '''import nu
import nu.kv
from nuspace.core.shapes import Space


def out(path):
    """Tick a counter in this app's own corner of the space's scratch kv."""
    key = path + ".ticks"
    now = nu.ToInt(Space.state.get_item(key, nu.Str("0")))
    tick = Space.state.set_item(key, nu.ToStr(now + nu.Int({step})))
    return nu.kv.auto_flow_atomic(
        Space.state.set_item(key, nu.Str("0")) >> nu.ForeverDo(nu.DelayedDo(0.1, tick)),
        scope=Space,
    )
'''

# Reads another app's counter and copies it into its own namespace. Two apps,
# two processes, both reaching the one store through their own proxy.
MIRROR = '''import nu
import nu.kv
from nuspace.core.shapes import Space


def out(path):
    """Copy another app's tick count into this one's namespace."""
    src = "apps.{watched}.ticks"
    dst = path + ".seen"
    copy = Space.state.set_item(dst, nu.ToStr(Space.state.get_item(src, nu.Str("0"))))
    return nu.kv.auto_flow_atomic(nu.ForeverDo(nu.DelayedDo(0.1, copy)), scope=Space)
'''


def write(app_id, source):
    """One app into the store, as the editor would write it."""
    app = Space.apps[app_id]
    return (
        app.name.set(nu.Str(app_id))
        >> app.policy.set(nu.Str("always"))
        >> app.snippet.set(nu.Str(source))
    )


def report(label):
    """What the runner and the apps have to say for themselves, right now."""
    return nu.Print(STDOUT, label, "\n  workers:", Runner.workers, "\n  state:  ") >> nu.Print(
        STDOUT, "   ", nu.dict(Space.state.items())
    )


# The demo, as one tree, running beside the live loop after the seed pass.
#
# The waits are generous on purpose: the subscription is depth-unbounded, so
# writing an app's three fields costs three reconciles, each a kill + spawn +
# dispatch. That churn is why the worker ids below are not 0 and 1.
SCRIPT = (
    nu.DelayedDo(0.2, write("a_counter", COUNTER.format(step=1)))
    >> nu.DelayedDo(0.2, write("a_mirror", MIRROR.format(watched="a_counter")))
    >> nu.DelayedDo(4.0, report("\n[1] both apps up and running"))
    # Edit one snippet. Only the counter restarts: its worker id moves, the
    # mirror's does not, and the counter starts over from zero stepping by
    # ten.
    >> nu.DelayedDo(0.2, Space.apps["a_counter"].snippet.set(nu.Str(COUNTER.format(step=10))))
    >> nu.DelayedDo(2.0, report("\n[2] counter edited, mirror untouched"))
    # Delete one app. Its worker is killed and forgotten; the counter keeps
    # ticking and the mirror's value simply stops moving.
    >> nu.DelayedDo(0.2, Space.apps.del_item(nu.Str("a_mirror")))
    >> nu.DelayedDo(2.0, report("\n[3] mirror deleted, counter undisturbed"))
)


def demo():
    shutil.rmtree(ROOT, ignore_errors=True)
    ROOT.mkdir(parents=True, exist_ok=True)
    asyncio.run(run_apps(str(ROOT / "db"), alongside=SCRIPT, duration=12.0))


if __name__ == "__main__":
    sys.exit(demo())
