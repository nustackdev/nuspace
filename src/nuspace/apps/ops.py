"""Write + read primitives over the apps store.

Every one returns a Nu tree and nothing else, so a ui, a cli or an agent
composes them instead of hand-writing ref chains. ``root`` is the space's own
root Shape class: ``Space.apps`` and ``DemoSpace.apps`` are different
addresses, so an op against a subclassed space has to be told which one.

Write:
- :func:`add_app`     -- every field of a new app, in one tree.
- :func:`remove_app`  -- drop the row. The runner kills the worker.
- :func:`set_snippet` / :func:`rename_app` / :func:`set_policy` -- one field.

Read:
- :func:`app_ids` / :func:`exists` / :func:`snippet_of` / :func:`error_of`
  -- the store.
- :func:`running` / :func:`is_running` -- the host's ``Runner.workers``, which
  is mem and therefore only readable from inside the runner's own tree.
"""

from __future__ import annotations

import nu
from nuspace.core.ids import mint_ordered_id
from nuspace.core.shapes import Space

from .shapes import DEFAULT_POLICY, Runner


__all__ = [
    "add_app",
    "app_ids",
    "error_of",
    "exists",
    "is_running",
    "remove_app",
    "rename_app",
    "running",
    "set_policy",
    "set_snippet",
    "snippet_of",
]


def _state_key(app_id: nu.StrArg, suffix: str) -> nu.Nu:
    """``apps.<app_id><suffix>`` as a term, for either a python str or a term."""
    return nu.Str("apps.") + app_id + nu.Str(suffix)


# --- write -----------------------------------------------------------------


def add_app(
    source: nu.StrArg,
    *,
    app_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    policy: nu.StrArg = DEFAULT_POLICY,
    root: type[Space] = Space,
) -> nu.Nu:
    """Write a whole app: id, name, policy and source, in one tree.

    Args:
        source: the snippet, a ``nu.prog`` module with an ``out`` entry point.
        app_id: the app's key. Minted in creation order when absent, in which
            case the caller never learns it -- pass ``mint_ordered_id("a")``
            yourself if you mean to address the app afterwards.
        name: what to call it. Defaults to the id.
        policy: when it runs. Nothing reads it yet.
        root: the space's root Shape class.
    """
    # Minted while the tree is built, not while it runs, so re-running one tree
    # rewrites one app rather than adding another.
    app_id = mint_ordered_id("a") if app_id is None else app_id
    app = root.apps[app_id]
    # Snippet last: every field write wakes its own reconcile, so this order
    # leaves the pass that actually launches the app holding the final source.
    return (
        app.name.set(app_id if name is None else name)
        >> app.policy.set(policy)
        >> app.snippet.set(source)
    )


def remove_app(app_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Drop an app from the store. A no-op when it is not there."""
    # Guarded rather than bare: del_item on a missing key raises, and removing
    # something already gone is exactly what a retried ui click does.
    return nu.IfDo(root.apps.contains(app_id), root.apps.del_item(app_id))


def set_snippet(app_id: nu.StrArg, source: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Replace an app's source. The runner restarts that app and no other."""
    return root.apps[app_id].snippet.set(source)


def rename_app(app_id: nu.StrArg, name: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Replace an app's display name. The id does not move."""
    return root.apps[app_id].name.set(name)


def set_policy(app_id: nu.StrArg, policy: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Replace an app's policy string."""
    return root.apps[app_id].policy.set(policy)


# --- read ------------------------------------------------------------------


def app_ids(*, root: type[Space] = Space) -> nu.Nu:
    """Every app id in the space, as a list."""
    # nu.list, not the bare keys view: the view is lazy and dies with its
    # Snapshot, so an undrained one reads as StorageClosedError later.
    return nu.list(root.apps.keys())


def exists(app_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """Whether the store has an app under this id."""
    return root.apps.contains(app_id)


def snippet_of(app_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """An app's source, verbatim. EMPTY when there is no such app."""
    return root.apps[app_id].snippet


def error_of(app_id: nu.StrArg, *, root: type[Space] = Space) -> nu.Nu:
    """The construction error the runner recorded for this app, or ``""``.

    Written by ``app_body`` when a snippet does not construct, since a
    dispatched body has no waiter to raise into.
    """
    return root.state.get_item(_state_key(app_id, ".error"), nu.Str(""))


def running() -> nu.Nu:
    """Which apps have a worker, and its pool id, as a dict.

    ``Runner.workers`` is mem in the host process, so this only answers inside
    the runner's own tree.
    """
    return nu.dict(Runner.workers.items())


def is_running(app_id: nu.StrArg) -> nu.Nu:
    """Whether this app has a worker on record right now."""
    return Runner.workers.contains(app_id)
