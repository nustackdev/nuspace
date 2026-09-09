"""The Apps pillar: ops orchestration.

Three pieces, and the split between them is the point.

- ``AppsRunner`` goes in the **space's** tree. It owns the supervisor for
  the life of the space, so apps run with no browser attached.
- ``AppsRuntime`` is what it owns: the supervisor plus the reconcile loop
  plus the status fan-out. Drivers find it by root Shape class.
- ``AppsRef`` / ``AppsDriver`` go in the **connection's** ui tree. They
  observe the runtime and edit kv. They never run anything.
"""

from nuspace.web.refs.apps.apps import AppsDriver, AppsRef
from nuspace.web.refs.apps.runner import AppsRunner
from nuspace.web.refs.apps.runtime import AppsRuntime, get_runtime
from nuspace.web.refs.apps.supervise import AppSpec, AppsSupervisor


__all__ = [
    "AppSpec",
    "AppsDriver",
    "AppsRef",
    "AppsRunner",
    "AppsRuntime",
    "AppsSupervisor",
    "get_runtime",
]
