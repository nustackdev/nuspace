"""Apps: the nuspace ops surface.

    ref.py            the wire handle, and nothing else
    ops.py            one ref per op; the path is the dispatch
    interactions/     app.py  ship.py
    view.py           one connection's observation of the space runtime
    store.py          walking the apps substrate
    control.py        composes the above into one per-connection program

Three pieces span two lifetimes, and the split between them is the point.

- ``AppsRunner`` goes in the **space's** tree. It owns the supervisor for
  the life of the space, so apps run with no browser attached.
- ``AppsRuntime`` is what it owns: the supervisor plus the reconcile loop
  plus the status fan-out. Drivers find it by root Shape class.
- ``AppsRef`` / ``AppsDriver`` go in the **connection's** ui tree. They
  observe the runtime and edit kv. They never run anything.
"""

from nuspace.web.refs.apps.control import AppsDriver
from nuspace.web.refs.apps.ref import AppsRef
from nuspace.web.refs.apps.runner import AppsRunner
from nuspace.web.refs.apps.runtime import AppsRuntime, get_runtime
from nuspace.web.refs.apps.store import new_app_source
from nuspace.web.refs.apps.supervise import AppSpec, AppsSupervisor
from nuspace.web.refs.apps.view import View


__all__ = [
    "AppSpec",
    "AppsDriver",
    "AppsRef",
    "AppsRunner",
    "AppsRuntime",
    "AppsSupervisor",
    "View",
    "get_runtime",
    "new_app_source",
]
