"""Services: the system's policy, as cells on workers (D20).

Each is a system plane with a fixed id and one cell ``main`` (D31) whose
prog is a shim importing its module here, so the code lives in the package
and the store holds a program like any other. They act only through ops.

- :mod:`.init`: pid 1, brings up its boot list at open.
- :mod:`.nav`: one worker per open plane of a connection, running the planes its routes name.
- :mod:`.supervisor`: restarts the cells its policy names, with backoff.
- :mod:`.reload`: replaces a live run when its cell's prog changes.
- :mod:`.bootstrap`: the service planes made real in a store.

Modules here are imported into workers: nothing at module scope may pull in
a server (fastapi, uvicorn).
"""

from . import init, nav, reload, supervisor
from .bootstrap import BOOTED, SERVICES, ensure_system
from .init import Boot, boot, unboot
from .supervisor import ALWAYS, ON_FAILURE, POLICIES, Policy, supervise, unsupervise


__all__ = [
    "ALWAYS",
    "BOOTED",
    "ON_FAILURE",
    "POLICIES",
    "SERVICES",
    "Boot",
    "Policy",
    "boot",
    "ensure_system",
    "init",
    "nav",
    "reload",
    "supervise",
    "supervisor",
    "unboot",
    "unsupervise",
]
