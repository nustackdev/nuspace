"""nav: the driver that runs what the panes show. One arm per open pane.

For each pane in ``Conn.connections[sid].panes``, nav adds a plane run of
its plane inside the tab's session (``plane_run.add`` with
``envs=[["session", sid]]``) and records it in the pane
(``Pane.plane_run``):

    pane opened        a plane run added, recorded in the pane
    restart asked      (a new ``Pane.restart`` token) the run stopped, a
                         fresh one added
    pane closed        its run stopped
    tab closed         every pane's run stopped
    run over           nothing: a finished run stays finished, its drawn
                         output stays. Restarting is the supervisor's job

So a run starts only when a pane opens or its restart token changes, never
because none is live. Cells added to a live run's plane get their first
run from reload; a removed plane's runs are stopped by the kernel.

The stop wraps the start, so a pane closed mid start, a tab going and nav
itself stopping all leave nothing live behind. A start that raises (the
plane removed or not runnable) is reported and the pane waits for its next
restart token: nav catches per pane and never ends for one.

Level, with re-checks: the folds over tabs and panes and the wait on the
restart token re-read the store on the standard schedule, so a missed
notification is late, never lost. nav runs beside the web device, in the
host: it needs Conn, which only the host and its workers bind.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace.ops.brackets import atomic
from nuspace.utils.policies import report, restarting

from .interactions import SESSION_ENV
from .shapes import Conn


__all__ = ["BY", "nav", "pane"]


#: What plane runs nav adds are recorded as ``by``.
BY = "nav"

_RECHECK = {"after": nu.RECHECK_AFTER, "every": nu.RECHECK_EVERY}

_tabs = Conn.connections


def _listed(ids: nu.Nu) -> nu.Nu:
    """A dict's keys as a list, ``[]`` when it is gone."""
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


def _turn(sid: nu.Str, plane: nu.Str, token: nu.Str) -> nu.Nu:
    """One plane run of the pane: added, recorded, held until the token moves off ``token``, stopped.

    The stop runs on every way out, from the start of the add on: before
    the add lands ``made`` reads ``""``, which stops nothing.
    """
    panes = _tabs[sid].panes
    asked = panes[plane].restart
    envs = nu.List.of(nu.List.of(SESSION_ENV, sid))

    def held(made: nu.ObjectRef) -> nu.Nu:
        run = nu.Str(made)
        start = atomic(nuspace.plane_run.add(plane, by=BY, envs=envs, into=made))
        # The pane may have closed meanwhile: never write a pane back into being.
        open_now = nu.If(panes.exists(), panes.contains(plane), False)
        remember = atomic(nu.IfDo(open_now, panes[plane].plane_run.set(run)))
        failed = nu.TryCatch(start >> remember, catch=lambda err: report("nav", plane, err))
        # Watched from the tabs, which always exist: a closed tab's row is deleted.
        moved = nu.WaitUntil(
            atomic(_tabs.on_child_change(sid)), atomic(asked.fallback("") != token), **_RECHECK
        )
        stop = nu.IfDo(run != "", atomic(nuspace.plane_run.stop(run)))
        return nu.TryCatch(failed >> moved, finally_=stop)

    return nu.let("", held)


def pane(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """One open pane: a run per restart token, for as long as the pane is open. Never returns.

    Cancelled when the pane closes, which stops its run.
    """
    sid, plane = nu.Str(sid), nu.Str(plane)
    asked = _tabs[sid].panes[plane].restart
    turn = nu.let(atomic(asked.fallback("")), lambda token: _turn(sid, plane, nu.Str(token)))
    return nu.ForeverDo(restarting(turn, "nav", plane))


def _tab(sid: nu.Str) -> nu.Nu:
    """One tab: :func:`pane` per pane, opens and closes included. Never returns."""
    panes = _tabs[sid].panes
    return nu.ReconcileLatestEach(
        atomic(_listed(panes)),
        # The tab's whole row, watched from the tabs: a closed tab's row is deleted.
        atomic(_tabs.on_child_change(sid)),
        lambda plane: pane(sid, nu.Str(plane)),
        **_RECHECK,
    )


def nav() -> nu.Nu:
    """The nav driver: :func:`pane` for every pane of every open tab. Never returns.

    Needs the stores bound (Space and Conn), and the kernel beside it to
    make the plane runs it adds true. Only the web device runs it.
    """
    return nu.ReconcileLatestEach(
        atomic(_listed(_tabs)),
        atomic(_tabs.on_children_change()),
        lambda sid: restarting(_tab(nu.Str(sid)), "nav", nu.Str(sid)),
        **_RECHECK,
    )
