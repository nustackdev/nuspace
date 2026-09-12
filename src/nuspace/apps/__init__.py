"""nuspace.apps -- every app in the space, running, as one Nu tree.

Module layout:

- :mod:`.shapes` -- store layout (``App``) and the host's own ``Runner``.
- :mod:`.ops`    -- write + read primitives (``add_app`` / ``snippet_of`` / ...).
  What a ui, a cli or an agent calls instead of writing ref chains.
- :mod:`.runner` -- the driver: seed, reconcile, live loop, ``run_apps``.

No ``interactions`` module: every op here is a plain ``-> Nu`` function over
existing atoms, and nothing in this layer touches the host directly.
"""

from __future__ import annotations

from .ops import (
    add_app,
    app_ids,
    error_of,
    exists,
    is_running,
    remove_app,
    rename_app,
    running,
    set_policy,
    set_snippet,
    snippet_of,
)
from .runner import (
    CHANGED_APP_INDEX,
    DEFAULT_CHANNEL_PREFIX,
    app_body,
    apps_tree,
    changed_app,
    driver,
    free_port,
    reconcile,
    run_apps,
    worker_init,
)
from .shapes import DEFAULT_POLICY, App, Runner


__all__ = [
    "CHANGED_APP_INDEX",
    "DEFAULT_CHANNEL_PREFIX",
    "DEFAULT_POLICY",
    "App",
    "Runner",
    "add_app",
    "app_body",
    "app_ids",
    "apps_tree",
    "changed_app",
    "driver",
    "error_of",
    "exists",
    "free_port",
    "is_running",
    "reconcile",
    "remove_app",
    "rename_app",
    "run_apps",
    "running",
    "set_policy",
    "set_snippet",
    "snippet_of",
    "worker_init",
]
