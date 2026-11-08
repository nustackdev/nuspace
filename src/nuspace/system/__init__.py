"""The system planes: planes shipped with nuspace, running, not removable. One folder each.

- :mod:`.init`: starts the planes on its boot list when the space opens.
- :mod:`.supervisor`: restarts planes whose runs end, per policy.
- :mod:`.reload`: keeps live plane runs on the latest code.
- :mod:`.reactions`: runs a plane when something changes.

Each folder holds its own ``shapes`` (its state, in its plane's state), its
``ops`` and its ``plane`` (ids, cells, driver). They run without any device.
:func:`ensure` makes them where missing and :func:`start` asks for init's
run: the host calls both at open.

Namespaced, never re-exported at the top: ``nuspace.system.supervisor.supervise(...)``.
"""

from . import init, reactions, reload, supervisor
from .planes import PLANES, ensure, start


__all__ = ["PLANES", "ensure", "init", "reactions", "reload", "start", "supervisor"]
