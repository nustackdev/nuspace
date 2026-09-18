"""When and what to run.

A driver composes the runtime language into an answer to two questions: which
Planes are up, and what they draw on while they are. The runtime language
answers neither. It places Cells and keeps them alive, and takes both answers
as arguments.

:mod:`nuspace.drivers.headless` is the whole of it for now: a Plane is up
because its ``trigger`` says a process opening the Space is enough, and
nothing is drawn.
"""

from nuspace.drivers.headless import BOOT_TRIGGERS, run_space, triggered_by


__all__ = [
    "BOOT_TRIGGERS",
    "run_space",
    "triggered_by",
]
