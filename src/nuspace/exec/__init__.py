"""Out-of-process execution and supervision for nuspace sections.

A page is a supervision group. A section is a worker process. Opening a
page acquires one pre-warmed worker per section; each worker compiles its
own source and drives its own Nu tree, so one section erroring or hanging
is isolated to that section and editing one section restarts one section.

Sections are processes rather than tasks for one reason: teardown has to
be guaranteed. Cancellation is cooperative and always will be, so an
in-process section wedged in a tight loop or a C call can only be
abandoned. A process gets SIGTERM then SIGKILL and the bound is a number
we choose.

Headless. Nothing here imports the web shell.

    >>> from nuspace.exec import SectionSpec, Supervisor
    >>> sup = Supervisor(host, pool_size=8)          # doctest: +SKIP
    >>> await sup.astart()                           # doctest: +SKIP
    >>> await sup.open_page("p1", [SectionSpec("s1", src)])   # doctest: +SKIP
"""

from __future__ import annotations

from .compile import construct_section, enumerate_ui_refs, section_filename, wire_type
from .handle import Timeouts, WorkerHandle
from .hosts import LoopbackHost, SessionHost
from .pool import WarmPool
from .session import WorkerSession
from .status import (
    STATES,
    SectionSpec,
    SectionState,
    SectionStatus,
    StatusEvent,
    StatusStream,
)
from .supervisor import Supervisor, UiHost


__all__ = [
    "STATES",
    "LoopbackHost",
    "SectionSpec",
    "SectionState",
    "SectionStatus",
    "SessionHost",
    "StatusEvent",
    "StatusStream",
    "Supervisor",
    "Timeouts",
    "UiHost",
    "WarmPool",
    "WorkerHandle",
    "WorkerSession",
    "construct_section",
    "enumerate_ui_refs",
    "section_filename",
    "wire_type",
]
