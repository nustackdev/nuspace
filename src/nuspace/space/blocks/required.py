"""A requirement: what an entry point needs running before it starts, or a refusal saying what to start.

The layers of a space assume the ones under them and never check: a
driver fails as it fails when what it runs on goes. So the check lives in
the entry point, once, at setup: the kernel's needs infra answering,
web's needs a kernel running. :class:`Required` is that check as a
bracket. It binds nothing.

A requirement may be coming up beside the entry point, eg two shells
started at once, or a supervisor starting its children in order. So it
looks again for a moment before it refuses: a short ``grace`` always,
and up to ``wait`` seconds while ``waiting()`` says it is on its way
(a lock held, its server not up yet).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from nuspace.errors import Refused


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Context


__all__ = ["EVERY", "Required"]


#: How often a requirement looks again while it waits.
EVERY = 0.05


class Required:
    """``check()`` holding at setup, or within ``wait`` seconds, else a refusal. Binds nothing.

    It looks again while less than ``grace`` seconds have passed, or less
    than ``wait`` and ``waiting()`` holds.

    Args:
        check: Whether the requirement holds now.
        refusal: What a refusal says, eg ``"infra of this space is not
            running: start it first"``.
        wait: Seconds to wait at most.
        waiting: Whether what is required is on its way, asked at each
            look. None waits the whole ``wait``.
        grace: Seconds to look again whatever ``waiting()`` says: for
            what is required starting beside this, not showing it yet.

    Raises:
        Refused: ``check()`` did not hold in time.
    """

    def __init__(
        self,
        check: Callable[[], bool],
        refusal: str,
        wait: float = 10.0,
        waiting: Callable[[], bool] | None = None,
        grace: float = 0.0,
    ) -> None:
        self.check = check
        self.refusal = refusal
        self.wait = wait
        self.waiting = waiting
        self.grace = grace

    def _hold_on(self, since: float) -> bool:
        passed = time.monotonic() - since
        if passed >= self.wait:
            return False
        return passed < self.grace or self.waiting is None or self.waiting()

    def setup(self, ctx: Context) -> None:
        """Look until ``check()`` holds, or refuse."""
        since = time.monotonic()
        while not self.check():
            if not self._hold_on(since):
                raise Refused(self.refusal)
            time.sleep(EVERY)

    async def asetup(self, ctx: Context) -> None:
        """Look until ``check()`` holds, or refuse, sleeping between looks on the loop."""
        since = time.monotonic()
        while not self.check():
            if not self._hold_on(since):
                raise Refused(self.refusal)
            await asyncio.sleep(EVERY)
