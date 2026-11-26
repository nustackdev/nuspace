"""nav: the driver that runs what the panes show. One arm per open pane.

For each pane in ``Conn.connections[sid].panes``, nav adds a plane run of
its plane inside the tab's session (``plane_run.add`` with
``envs=[["session", sid]]``) and records it in the pane
(``Pane.plane_run``):

    pane opened        a plane run added, recorded in the pane
    restart asked      (a new ``Pane.restart`` token) the run stopped, a
                         fresh one added
    run gone           (ended by a kernel's close or reap, or no row) a
                         fresh one added
    pane closed        its run stopped
    tab closed         every pane's run stopped
    run over           nothing: a run that failed or finished stays so, its
                         drawn output stays. Restarting is the supervisor's job

Level: an open pane wants one live run. A run a kernel ended without
anyone asking (:data:`~nuspace.kernel.CLOSED` at a clean stop,
:data:`~nuspace.kernel.LEFT_OVER` at the reap after a crash) is asked for
again, and the next kernel to run starts it, so web never cares when the
kernel restarts. A run that ended any other way waits for the restart
token, so a plane that crashes never loops.

A pane on a plane that is not in the space or not on the web (one the
viewer says is missing or headless) waits for that to change before its
run: opening a plane in a browser never runs one that has no view. Cells
added to a live run's plane get their first run from reload; a removed
plane's runs are stopped by the kernel.

The stop wraps the start, so a pane closed mid start, a tab going and nav
itself stopping all leave nothing live behind. A start that raises (the
plane removed or not runnable) is reported and the pane waits for its next
restart token: nav catches per pane and never ends for one.

Re-checks: the folds over tabs and panes and the waits re-read the store
on the standard schedule, so a missed notification is late, never lost.
nav runs in web's driver, beside the tabs it serves.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace.kernel import CLOSED, LEFT_OVER
from nuspace.ops.brackets import atomic
from nuspace.utils import keys_of
from nuspace.utils.policies import report, restarting

from .interactions import SESSION_ENV
from .shapes import Conn, Web


__all__ = ["BY", "nav", "pane", "stop_left"]


#: What plane runs nav adds are recorded as ``by``.
BY = "nav"

_RECHECK = {"after": nu.RECHECK_AFTER, "every": nu.RECHECK_EVERY}

_tabs = Conn.connections

_runs = nuspace.Space.exec.plane_runs


def _gone(run: nu.Str) -> nu.Bool:
    """Whether ``run`` was ended by a kernel and not by anyone asking: no row, or ``CLOSED``/``LEFT_OVER``.

    ``""`` (no run was added: its start failed) is never gone, so a failing
    start waits for the restart token.
    """
    row = _runs[run]
    error = row.error.fallback("")
    by_kernel = row.ended_at.exists().and_((error == CLOSED).or_(error == LEFT_OVER))
    return (run != "").and_(nu.Bool(nu.If(_runs.contains(run), by_kernel, True)))


def stop_left() -> nu.Nu:
    """Every live plane run nav asked for, stopped. One commit. Cost: O(live plane runs).

    Run as web starts, after Conn is cleared: no tab of a web before
    survives, so nothing should draw on one.
    """
    live = keys_of(nuspace.Space.exec.indexes.live.plane_runs)

    def stopped(at: nu.Nu) -> nu.Nu:
        run = nu.Str(at)
        return nu.IfDo(_runs[run].by.fallback("") == BY, nuspace.plane_run.stop(run))

    return atomic(nu.ForEachDo(live, stopped))


def _turn(sid: nu.Str, plane: nu.Str, token: nu.Str) -> nu.Nu:
    """One plane run of the pane: added, recorded, held until the token moves off ``token`` or the run is gone, stopped.

    The stop runs on every way out, from the start of the add on: before
    the add lands ``made`` reads ``""``, which stops nothing.
    """
    panes = _tabs[sid].panes
    asked = panes[plane].restart
    envs = nu.List.of(nu.List.of(SESSION_ENV, sid))

    # A plane made in the same breath lands its Space row, then its web row.
    shown = nuspace.plane.exists(plane).and_(Web.planes.contains(plane))
    landing = nu.OnAny(nuspace.Space.planes.on_children_change(), Web.planes.on_children_change())
    on_web = nu.WaitUntil(atomic(landing), atomic(shown), **_RECHECK)

    def held(made: nu.ObjectRef) -> nu.Nu:
        run = nu.Str(made)
        start = on_web >> atomic(nuspace.plane_run.add(plane, by=BY, envs=envs, into=made))
        # The pane may have closed meanwhile: never write a pane back into being.
        open_now = nu.If(panes.exists(), panes.contains(plane), False)
        remember = atomic(nu.IfDo(open_now, panes[plane].plane_run.set(run)))
        failed = nu.TryCatch(start >> remember, catch=lambda err: report("nav", plane, err))
        # The tab watched from the tabs, which always exist: a closed tab's row is deleted.
        changed = nu.OnAny(_tabs.on_child_change(sid), _runs[run].on_change())
        over = (asked.fallback("") != token).or_(_gone(run))
        moved = nu.WaitUntil(atomic(changed), atomic(over), **_RECHECK)
        stop = nu.IfDo(run != "", atomic(nuspace.plane_run.stop(run)))
        return nu.TryCatch(failed >> moved, finally_=stop)

    return nu.let(held, made="")


def pane(sid: nu.StrArg, plane: nu.StrArg) -> nu.Nu:
    """One open pane: a run per restart token or gone run, for as long as the pane is open. Never returns.

    Cancelled when the pane closes, which stops its run.
    """
    sid, plane = nu.Str(sid), nu.Str(plane)
    asked = _tabs[sid].panes[plane].restart
    turn = nu.let(lambda token: _turn(sid, plane, nu.Str(token)), token=atomic(asked.fallback("")))
    return nu.ForeverDo(restarting(turn, "nav", plane))


def _tab(sid: nu.Str) -> nu.Nu:
    """One tab: :func:`pane` per pane, opens and closes included. Never returns."""
    panes = _tabs[sid].panes
    return nu.ReconcileLatestEach(
        atomic(keys_of(panes)),
        # The tab's whole row, watched from the tabs: a closed tab's row is deleted.
        atomic(_tabs.on_child_change(sid)),
        lambda plane: pane(sid, nu.Str(plane)),
        **_RECHECK,
    )


def nav() -> nu.Nu:
    """The nav driver: :func:`pane` for every pane of every open tab. Never returns.

    Needs the stores bound (Space and Conn), and a kernel somewhere to
    make the plane runs it adds true; none up, they wait for the next.
    Only web's driver runs it.
    """
    return nu.ReconcileLatestEach(
        atomic(keys_of(_tabs)),
        atomic(_tabs.on_children_change()),
        lambda sid: restarting(_tab(nu.Str(sid)), "nav", nu.Str(sid)),
        **_RECHECK,
    )
