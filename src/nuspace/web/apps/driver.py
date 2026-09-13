"""The apps driver: one ``ReactForever`` arm per interaction, all in parallel.

This is the whole web layer for apps, and it is flat on purpose. Every arm is
one subscription wired to one thing, and there is no dispatch anywhere in it:
no ``op`` string to switch on, no table of handlers, no python callable
smuggled into an atom. Two families, and an arm belongs to exactly one:

- **browser -> kv.** An ``AppsRef`` event fires; the arm runs one
  :mod:`nuspace.apps.ops` call over the event's own fields.
- **kv -> browser.** A container changes; the arm ships one ``AppsRef``
  write, carrying the whole current answer.

No ``NavRef`` here, and that is the shape of the pillar rather than a cut.
Apps are flat, so the surface is one list and every frame carries all of it;
there is no per-view page id to read back off the browser the way the pages
driver has to.

Nothing here reaches into :mod:`nuspace.apps.runner`. The web layer writes kv
through ``ops``; the runner is subscribed to the same store and hears its own
changes. That is the separation, and it is why a restart is spelled "write
the snippet again" rather than "tell the runner something".

**Every arm is long-lived by construction.** The ws endpoint races the
connection against this tree and closes the socket when either finishes, so a
tree that completes drops the browser. What keeps that true -- the double
guard, the per-arm attrs namespace, the fresh subscription -- is
:mod:`nuspace.web.arms`, shared with the pages driver. Arm names are prefixed
``app_`` so a composition holding both drivers cannot have two arms binding
one attrs key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.kv
from nuspace._root import resolve_root
from nuspace.apps import ops
from nuspace.web.arms import Arms, field_str


if TYPE_CHECKING:
    from nu.domains.shape import Shape
    from nuspace.web.apps.ref import AppsRef


__all__ = ["ARMS", "apps_driver"]


#: How many arms the composition folds. Pinned so a new interaction that
#: forgets its arm, or an arm that quietly loses its subscription, says so.
ARMS = 9


#: Every arm in this module, labelled for the reports it prints.
_arms = Arms("apps")


def apps_driver(
    apps: AppsRef,
    *,
    root: type[Shape] | None = None,
    attached: bool | None = None,
) -> nu.Nu:
    """The apps surface, live, as one tree. Built per connection.

    Args:
        apps: the ``AppsRef`` on the mounted shell, already bound to its
            screen so its wire path resolves.
        root: the space's root Shape class.
        attached: whether a runner is supervising apps in this process.
            ``None``, the default, reads it -- ``ops.attached()`` is mem, so
            it answers True exactly where the runner's own bookkeeping is and
            False everywhere else, and it is re-read on every frame rather
            than guessed when the tree is built. A bool pins it instead, for a
            caller that is assembling something and not asking.

    Returns:
        The tree, bracketed for atomicity against ``root``. It never
        finishes, which is the contract the ws endpoint holds it to.
    """
    root = resolve_root(root)

    # Built per use, never bound once and dropped into four arms: a Nu node is
    # a value, and one object sitting in four tree positions is one compiled
    # node four arms then share at runtime. The live read is a term, so it
    # obeys the same rule as the rest of them.
    def supervised() -> nu.Nu | bool:
        return ops.attached() if attached is None else attached

    def rows() -> nu.Nu:
        return apps.set_apps(ops.app_rows(root=root), attached=supervised())

    def statuses() -> nu.Nu:
        return apps.set_status(ops.app_statuses(supervised=supervised(), root=root))

    # A cold store has no apps container, and a subscription over a missing
    # container resolves to INVALID and silently never fires. Idempotent, so a
    # tab stays self-sufficient without a seed script having been run first.
    boot = ops.init_apps(root=root) >> rows() >> statuses()

    flow = (
        # -- browser -> kv ---------------------------------------------------
        _arms.event(
            "app_create",
            apps.on_create(),
            ops.add_app(
                field_str("app_create", "source"),
                app_id=field_str("app_create", "app_id"),
                name=field_str("app_create", "name"),
                root=root,
            ),
        )
        | _arms.event(
            "app_rename",
            apps.on_rename(),
            ops.rename_app(
                field_str("app_rename", "app_id"), field_str("app_rename", "name"), root=root
            ),
        )
        | _arms.event(
            "app_delete",
            apps.on_delete(),
            ops.remove_app(field_str("app_delete", "app_id"), root=root),
        )
        | _arms.event(
            "app_update",
            apps.on_update_snippet(),
            ops.set_snippet(
                field_str("app_update", "app_id"), field_str("app_update", "source"), root=root
            ),
        )
        # A restart is a write, not a message: the runner reconciles on any
        # change under the app's key, and the error the last launch recorded
        # goes first or the row would read `failed` forever. The write alone
        # is not enough any more -- reconcile compares the stored source with
        # the running one and a rewrite as itself reads as no change -- so the
        # record is dropped before it, which is what makes the write bite.
        | _arms.event(
            "app_restart",
            apps.on_restart(),
            _restart(field_str("app_restart", "app_id"), root),
        )
        # -- kv -> browser ---------------------------------------------------
        # Selection writes nothing and reads nothing app-specific: an app's
        # whole answer is one row in a list every frame carries in full, so
        # opening one is a reason to re-pull the batch and nothing more.
        | _arms.event("app_select", apps.on_select(), statuses())
        # One fresh subscription per arm, never a shared term: two arms
        # holding one Changed node would share one handle, and the first of
        # them to end would close it under the other.
        | _arms.state("app_list", root.apps.on_change(), rows())
        # Status has two sources and so two arms. An app appearing or going
        # changes the set of statuses; an app's error key changes one of
        # them. Neither subsumes the other, and an arm that tried to watch
        # both would be a branch.
        | _arms.state("app_rowstatus", root.apps.on_change(), statuses())
        | _arms.state("app_errors", root.state.on_change(), statuses())
    )
    return nu.kv.auto_flow_atomic(boot >> flow, scope=root)


def _restart(app_id: nu.Nu, root: type[Shape]) -> nu.Nu:
    """Write one app's snippet back to itself, which is what restarts it.

    A snippet write is a store change like any other, so the runner's live
    loop hears it and reconciles: the worker is killed and relaunched. Guarded
    on the app being there, because a retried click on a row that has since
    gone must not vivify an app out of an empty snippet.
    """
    return nu.IfDo(
        ops.exists(app_id, root=root),
        ops.clear_error(app_id, root=root)
        >> ops.set_snippet(app_id, nu.ToStr(ops.snippet_of(app_id, root=root)), root=root),
    )
