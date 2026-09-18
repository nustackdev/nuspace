"""When and what to run.

A driver composes the runtime language into an answer to two questions: which
Planes are up, and what they draw on while they are. The runtime language
answers neither. It places Cells and keeps them alive, and takes both answers
as arguments.

Two of them, and neither is special. :mod:`nuspace.drivers.headless` brings up
every Plane whose ``trigger`` says a process opening the Space is enough, and
draws nothing. :mod:`nuspace.drivers.web` holds the browser connections and
brings up the Plane a connection navigated to, drawn on that connection.

Only the headless names are re-exported here. The web driver reaches a web
framework, and a Cell's worker imports this package to find a Space, so it is
asked for by module name when it is wanted.
"""

from nuspace.drivers.headless import BOOT_TRIGGERS, run_space, triggered_by


__all__ = [
    "BOOT_TRIGGERS",
    "run_space",
    "triggered_by",
]
