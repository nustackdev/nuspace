"""The supervisor's own state: a policy per supervised plane, kept in its plane's state."""

from __future__ import annotations

import nu
import nustd.kv


__all__ = ["ALWAYS", "ON_FAILURE", "POLICIES", "Policy", "Supervised"]


#: Restart after a failed exit only.
ON_FAILURE = "on-failure"

#: Restart after an ok or a failed exit.
ALWAYS = "always"

#: The policies a plane can be supervised under.
POLICIES = (ON_FAILURE, ALWAYS)


class Supervised(nu.Shape):
    """One supervised plane: ``Policy.planes[plane]``.

    ``policy`` is one of :data:`POLICIES`. ``delay`` is the fixed wait in
    seconds before every restart, absent for the backoff. ``run`` is the
    plane run the supervisor last asked for, absent before the first: the
    only run of the plane it ever looks at, so runs others start (a tab's,
    a reaction's) are theirs.
    """

    policy = nustd.kv.StrRef.slot()
    delay = nustd.kv.FloatRef.slot()
    run = nustd.kv.StrRef.slot()


class Policy(nu.Shape):
    """The supervisor's state, at ``State.planes["supervisor"]``: the supervised planes by id."""

    planes = nustd.kv.DictRef.slot(Supervised)
