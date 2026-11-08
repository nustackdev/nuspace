"""``nuspace.system.supervisor``: the ops over the supervisor's policies.

Bare terms over the supervisor plane's state, the caller brackets them
(``nuspace.atomic``): each writes State and reads Space, one commit. The
driver (:mod:`.plane`) acts on what they write.
"""

from __future__ import annotations

import nu
from nuspace.errors import Exists, Missing, Refused
from nuspace.shapes import Space
from nuspace.utils.checks import live, refuse

from .plane import supervised
from .shapes import POLICIES


__all__ = ["supervise", "unsupervise"]


def _checked(policy: nu.StrArg, delay: nu.FloatArg | None) -> nu.Nu:
    """The policy is one of :data:`~.shapes.POLICIES` and the delay not negative. Literals at build.

    Raises:
        Refused: Any other policy, a negative delay.
    """
    if isinstance(policy, str) and policy not in POLICIES:
        msg = f"policy {policy!r} is none of {POLICIES}"
        raise Refused(msg)
    if isinstance(delay, (int, float)) and delay < 0:
        msg = f"delay {delay!r} is negative"
        raise Refused(msg)
    checks: nu.Nu = nu.Noop()
    if not isinstance(policy, str):
        unknown = nu.List.of(*POLICIES).contains(policy).not_()
        checks = refuse(unknown, Refused, "policy ", policy, " is unknown")
    if isinstance(delay, nu.Nu):
        checks = checks >> refuse(nu.Float(delay) < 0.0, Refused, "a negative delay")
    return checks


def supervise(
    plane: nu.StrArg,
    *,
    policy: nu.StrArg,
    delay: nu.FloatArg | None = None,
    exists_ok: bool = False,
) -> nu.Nu:
    """Put a plane under the supervisor: it runs now, and again when its run ends as ``policy`` says.

    A plane whose supervisor run is over (left down by its policy) is
    brought up again: supervising it asks for it to run. Cost: O(1), about
    4 reads and 3 keys.

    Args:
        plane: The plane.
        policy: :data:`~.shapes.ON_FAILURE` (restart after a failed exit) or
            :data:`~.shapes.ALWAYS` (after an ok or a failed one).
        delay: Seconds to wait before every restart. None: the backoff.
        exists_ok: An already supervised plane is fine: it gets the given
            policy and delay.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
        Exists: It is supervised already, unless ``exists_ok``.
        Refused: A policy none of ``POLICIES``, a negative delay. A literal at build.
    """
    checks = _checked(policy, delay)
    row = supervised()[plane]
    taken = refuse(row.policy.exists(), Exists, "plane ", plane, " is supervised already")
    run = row.run.fallback("")
    over = (run != "").and_(Space.exec.indexes.live.plane_runs.contains(run).not_())
    timing = row.delay.erase() if delay is None else row.delay.set(nu.float(delay))
    return (
        checks
        >> live(Space.planes, plane, "plane")
        >> (nu.Noop() if exists_ok else taken)
        >> row.policy.set(policy)
        >> timing
        >> nu.IfDo(over, row.run.erase())
    )


def unsupervise(plane: nu.StrArg, *, missing_ok: bool = False) -> nu.Nu:
    """Stop supervising a plane. A run already going is left alone. Cost: O(1), 3 keys.

    Args:
        plane: The plane. Its row is not read: a removed plane comes off too.
        missing_ok: A plane not supervised is fine.

    Raises:
        Missing: It is not supervised, unless ``missing_ok``.
    """
    planes = supervised()
    if missing_ok:
        return planes.del_item(plane, missing_ok=True)
    unknown = planes[plane].policy.exists().not_()
    return refuse(unknown, Missing, "plane ", plane, " is not supervised") >> planes.del_item(plane)
