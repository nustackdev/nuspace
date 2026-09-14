"""Write + read primitives over the apps store.

Every one returns a Nu tree and nothing else, so a ui, a cli or an agent
composes them instead of hand-writing ref chains. ``root`` is the space's own
root Shape class, resolved at call time by :func:`~nuspace._root.resolve_root`
so this module never needs ``Space`` while it is being imported.

Write:
- :func:`init_apps`   -- the container, once, on a cold store.
- :func:`add_app`     -- every field of a new app, in one tree.
- :func:`remove_app`  -- drop the row. The runner kills the worker.
- :func:`set_snippet` / :func:`rename_app` / :func:`set_policy` -- one field.
- :func:`clear_error` -- forget what the runner last recorded.

Read:
- :func:`app_ids` / :func:`exists` / :func:`snippet_of` / :func:`error_of`
  -- the store.
- :func:`running` / :func:`is_running` / :func:`attached` -- the host's own
  ``Runner``, which is mem and therefore only readable from inside the
  process the runner is in.
- whole rows, one dict per app: :func:`app_rows` / :func:`app_statuses`. What
  a rail or a status bar is filled from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nuspace._root import resolve_root
from nuspace.core.ids import mint_ordered_id

from .shapes import DEFAULT_POLICY, Runner


if TYPE_CHECKING:
    from nu.domains.shape import Shape


__all__ = [
    "add_app",
    "app_ids",
    "app_rows",
    "app_statuses",
    "attached",
    "clear_error",
    "error_of",
    "exists",
    "init_apps",
    "is_running",
    "remove_app",
    "rename_app",
    "running",
    "set_policy",
    "set_snippet",
    "snippet_of",
]


#: The name ``Map`` binds the current element under, and the ref that reads it.
_ITEM = "_na_item"
_item = nu.AnyAttrRef(_ITEM)


# --- write: the space ------------------------------------------------------


def init_apps(*, root: type[Shape] | None = None) -> nu.Nu:
    """Create the apps container if the store has none. Idempotent.

    A subscription over a missing container resolves to INVALID and silently
    never fires, so anything that means to watch ``apps`` boots through here
    first. ``Dict.create()``, not ``{}``: a literal is captured once at Form
    construction and shared across every evaluation of the term.
    """
    return resolve_root(root).apps.init(nu.Dict.create())


# --- write -----------------------------------------------------------------


def add_app(
    source: nu.StrArg,
    *,
    app_id: nu.StrArg | None = None,
    name: nu.StrArg | None = None,
    policy: nu.StrArg = DEFAULT_POLICY,
    root: type[Shape] | None = None,
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
    app = resolve_root(root).apps[app_id]
    # Snippet last: every field write wakes its own reconcile, so this order
    # leaves the pass that actually launches the app holding the final source.
    return (
        app.name.set(app_id if name is None else name)
        >> app.policy.set(policy)
        >> app.snippet.set(source)
    )


def remove_app(app_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Drop an app from the store. A no-op when it is not there."""
    apps = resolve_root(root).apps
    # Guarded rather than bare: del_item on a missing key raises, and removing
    # something already gone is exactly what a retried ui click does.
    return nu.IfDo(apps.contains(app_id), apps.del_item(app_id))


def set_snippet(app_id: nu.StrArg, source: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Replace an app's source. The runner restarts that app and no other."""
    return resolve_root(root).apps[app_id].snippet.set(source)


def rename_app(app_id: nu.StrArg, name: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Replace an app's display name. The id does not move."""
    return resolve_root(root).apps[app_id].name.set(name)


def set_policy(app_id: nu.StrArg, policy: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Replace an app's policy string."""
    return resolve_root(root).apps[app_id].policy.set(policy)


def clear_error(app_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Forget the construction error recorded for this app. A no-op when clean.

    Guarded rather than bare: an erase on a leaf nothing wrote raises, and an
    app that never failed has no error.
    """
    error = resolve_root(root).state[app_id].error
    return nu.IfDo(error.exists(), error.erase())


# --- read ------------------------------------------------------------------


def app_ids(*, root: type[Shape] | None = None) -> nu.Nu:
    """Every app id in the space, as a list."""
    # nu.list, not the bare keys view: the view is lazy and dies with its
    # Snapshot, so an undrained one reads as StorageClosedError later.
    return nu.list(resolve_root(root).apps.keys())


def exists(app_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """Whether the store has an app under this id."""
    return resolve_root(root).apps.contains(app_id)


def snippet_of(app_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """An app's source, verbatim. EMPTY when there is no such app."""
    return resolve_root(root).apps[app_id].snippet


def error_of(app_id: nu.StrArg, *, root: type[Shape] | None = None) -> nu.Nu:
    """The construction error the runner recorded for this app, or ``""``.

    Written by ``app_body`` when a snippet does not construct, since a
    dispatched body has no waiter to raise into.
    """
    error = resolve_root(root).state[app_id].error
    return nu.If(error.exists(), nu.ToStr(error), nu.Str(""))


def running() -> nu.Nu:
    """Which apps have a worker, and its pool id, as a dict.

    ``Runner.workers`` is mem in the host process, so this only answers inside
    the runner's own tree.
    """
    return nu.dict(Runner.workers.items())


def is_running(app_id: nu.StrArg) -> nu.Nu:
    """Whether this app has a worker on record right now."""
    return Runner.workers.contains(app_id)


def attached() -> nu.Nu:
    """Whether a runner is supervising apps in this very process. A live read.

    Total, and true only where the bookkeeping really is: the ``FabricExists``
    half answers False rather than raising where no ``dict`` is bound at all,
    and ``Runner.attached`` is mem, so a runner in another process cannot make
    this say yes.
    """
    return nu.And(nu.FabricRef(dict).exists(), nu.NotEmpty(Runner.attached))


# --- read: whole rows ------------------------------------------------------
#
# Both answer with a list of dicts rather than a scalar, so one read fills a
# rail or a status bar. They exist because a caller that wants every app would
# otherwise read the ids and then loop in its own language, which puts a python
# (or a javascript) for-loop back in the middle of what is meant to be one tree.


def app_rows(*, root: type[Shape] | None = None) -> nu.Nu:
    """Every app as ``{id, name, source, policy}``, one dict per app.

    Keys sort by mint time, so this is creation order with no order slot.
    """
    apps = resolve_root(root).apps
    app = apps[_item]
    return nu.Collect(
        nu.Map(
            # nu.list, not the bare keys view, for the reason app_ids gives.
            nu.list(apps.keys()),
            nu.Dict.of(id=_item, name=app.name, source=app.snippet, policy=app.policy),
            key=_ITEM,
        )
    )


def _live(supervised: nu.BoolArg) -> nu.Nu | None:
    """Whether the app ``Map`` is on has a worker, or None when nobody asked.

    ``supervised`` is ``False`` for a tree that must not touch mem at all, and
    a term for one that wants the answer read rather than assumed.
    """
    if supervised is False:
        return None
    running_now = is_running(nu.StrAttrRef(_ITEM))
    if supervised is True:
        return running_now
    return nu.And(supervised, running_now)


def app_statuses(*, supervised: nu.BoolArg = False, root: type[Shape] | None = None) -> nu.Nu:
    """Every app as ``{section_id, state, error, started_at}``, in the same order.

    ``section_id`` rather than ``app_id`` because this is the supervisor's
    contract, not the Apps surface's: an app and a section are the same
    substance and share one status shape. An app whose row holds an ``error``
    reads ``failed``.

    Args:
        supervised: whether ``Runner.workers`` is readable here, which it only
            is inside the runner's own tree. ``False`` never claims an app is
            running and never touches mem; ``True`` reads it outright; a term
            (see :func:`attached`) reads whether to read it, which is what a
            web driver that may or may not share a process with a runner wants.
        root: the space's root Shape class.
    """
    root = resolve_root(root)
    # The row of whichever app Map is on. A ref chain, so the app id is a
    # segment rather than a piece of a key somebody built with a dot.
    scratch = root.state[nu.StrAttrRef(_ITEM)]
    idle = nu.Str("idle")
    live = _live(supervised)
    quiet = idle if live is None else nu.If(live, nu.Str("running"), idle)
    return nu.Collect(
        nu.Map(
            app_ids(root=root),
            nu.Dict.of(
                section_id=_item,
                state=nu.If(scratch.error.exists(), nu.Str("failed"), quiet),
                # Total: an unwritten leaf reads EMPTY, and EMPTY is not a
                # string the browser can be handed.
                error=nu.If(scratch.error.exists(), nu.ToStr(scratch.error), nu.Str("")),
                started_at=nu.Int(0),
            ),
            key=_ITEM,
        )
    )
