"""Close: as a kernel stops cleanly, what it started and left live ends interrupted, so reap sees only crashes.

The last step of the kernel's driver, in its ``finally``, while
the stores and the worker pool are still bound. By then the kernel's folds
are cancelled and drained: every arm has run its own ``finally`` and let
its workers go, leaving their records to this. Every started plane run,
its cell runs and every worker still live are ended ``interrupted`` with
:data:`CLOSED`, in one commit; the guarded ends skip one ended meanwhile.
A plane run whose cell's last run failed ends ``failed``, as the kernel's
own end has it.

Asks stay: a plane run asked for and never started (an arm cancelled
before its first commit, or an ask landing as the kernel stops) is left
live and pending for the next kernel to start (:func:`.records.end_started`).

A body still finishing on a worker meanwhile finds its cell run ended and
keeps that end. The workers' processes are the pool's: it stops them
after this.

Walks the live indexes only, never history: O(what is live). Never blocks
a close: should the commit fail, that is reported on stderr, the records
are left live, and the next kernel's reap ends them.
"""

from __future__ import annotations

import nu
from nu.core.io import STDERR
from nuspace.ops.brackets import atomic
from nuspace.shapes import EXIT_INTERRUPTED

from .interactions import ErrorText
from .records import end_started


__all__ = ["CLOSED", "close"]


#: The error a run or worker live at a clean close is ended with.
CLOSED = "Kernel closed"


def close() -> nu.Nu:
    """End what the kernel started and left live ``interrupted``, with :data:`CLOSED`. Asks stay.

    One commit, its raise reported. Cost: O(what is live).
    """

    def failed(err: nu.Nu) -> nu.Nu:
        return nu.Print(
            STDERR, "nuspace close: could not end what was live: ", ErrorText(err), sep=""
        )

    return nu.TryCatch(atomic(end_started(EXIT_INTERRUPTED, CLOSED)), catch=failed)
