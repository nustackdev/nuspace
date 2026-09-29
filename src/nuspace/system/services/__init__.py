"""Services: the system's policy, as cells on workers (D20).

Each is a system plane with a fixed id and one cell ``main`` (D31) whose
prog is a shim importing its module here, so the code lives in the package
and the store holds a program like any other. They act only through ops.

- :mod:`.init`: pid 1, runs its boot list at open.
- :mod:`.nav`: one plane run per open plane of a connection, the planes its routes name.
- :mod:`.supervisor`: keeps the planes its policy names running, with backoff.
- :mod:`.reload`: replaces a live cell run when its cell's prog changes.
- :mod:`.reactions`: runs a plane whenever a change is notified. Its plane has no ``main``.
- :mod:`.bootstrap`: the service planes made real in a store.

Modules here are imported into workers: nothing at module scope may pull in
a server (fastapi, uvicorn).
"""

from . import init, nav, reactions, reload, supervisor
from .bootstrap import BOOTED, SERVICES, ensure_system
from .init import Boot, boot, unboot
from .reactions import disable_react, enable_react, up_plane
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
    "disable_react",
    "enable_react",
    "ensure_system",
    "init",
    "nav",
    "reactions",
    "reload",
    "supervise",
    "supervisor",
    "unboot",
    "unsupervise",
    "up_plane",
]
