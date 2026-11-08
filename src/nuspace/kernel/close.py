"""Close: at a clean close, whatever the live indexes list ended interrupted, so reap sees only crashes.

The host runs it once as the space closes (Ctrl+C, or its body
returning), in a ``finally`` inside the worker pool, before the stores
close. By then the drivers are cancelled and drained: every kernel arm has
run its own ``finally`` and let its workers go, leaving their records to
this. Every plane run, cell run and worker still live is ended
``interrupted`` with :data:`CLOSED`, in one commit; the guarded ends skip
one ended meanwhile. A plane run whose cell's last run failed ends
``failed``, as the kernel's own end has it.

A body still finishing on a worker meanwhile finds its cell run ended and
keeps that end. The workers' processes are the pool's: it stops them
after this.

Walks the live indexes only, never history: O(what is live). Never blocks
a close: should the commit fail, that is reported on stderr, the records
are left live, and the next open's reap ends them.
"""

from __future__ import annotations

import nu
from nu.core.io import STDERR
from nuspace.ops.brackets import atomic
from nuspace.shapes import EXIT_INTERRUPTED

from .interactions import ErrorText
from .records import end_live


__all__ = ["CLOSED", "close"]


#: The error a run or worker live at a clean close is ended with.
CLOSED = "Space closed"


def close() -> nu.Nu:
    """End everything live ``interrupted``, with :data:`CLOSED`. One commit, its raise reported.

    Cost: O(what is live).
    """

    def failed(err: nu.Nu) -> nu.Nu:
        return nu.Print(
            STDERR, "nuspace close: could not end what was live: ", ErrorText(err), sep=""
        )

    return nu.TryCatch(atomic(end_live(EXIT_INTERRUPTED, CLOSED)), catch=failed)
