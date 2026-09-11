"""The runner: the thing that runs Nu trees on workers, as one Nu tree.

Not a process pool that Nu talks to. The pool is provisioned by brackets in
the tree, dispatch is a ``Teleport`` term, and the whole thing is one
``arun`` at the bottom of :func:`nuspace.runner.launch.launch`.

    launch  -> the runnable: manifest, assembly, one arun
    pool    -> the store, the invisibles server, the workers, the plan
    dispatch-> an app as a subtree that runs somewhere else
    seed    -> putting apps into a store, and demo apps to put there

The whole surface is exported from here; deep imports do not appear at call
sites.
"""

from nuspace.runner.dispatch import app_body, app_path, fan_out, run_nu, slot_body
from nuspace.runner.launch import launch, manifest, runner_tree
from nuspace.runner.pool import (
    DEFAULT_CHANNEL_PREFIX,
    Slot,
    free_port,
    plan,
    pool,
    served,
    store,
    worker_init,
)
from nuspace.runner.seed import demo_apps, seed, seed_store


__all__ = [
    "DEFAULT_CHANNEL_PREFIX",
    "Slot",
    "app_body",
    "app_path",
    "demo_apps",
    "fan_out",
    "free_port",
    "launch",
    "manifest",
    "plan",
    "pool",
    "run_nu",
    "runner_tree",
    "seed",
    "seed_store",
    "served",
    "slot_body",
    "store",
    "worker_init",
]
