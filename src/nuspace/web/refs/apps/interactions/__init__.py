"""The Apps interactions, one module per subject.

- ``app``  -- create, rename, delete, update, restart, and the boot-time
  container init.
- ``ship`` -- the two outbound loops (apps, status) and the kv
  subscription that feeds the first.

The third subject, the runtime pair ``observe`` / ``wake``, is not a
module here: it is not a Nu term and has no wire path, it is how the
connection attaches to a supervisor it does not own. It lives on
``View``, next to the listener it moves.

Each body takes named arguments. The op path carries which interaction,
the payload carries only its arguments, so nothing here asks what op it
is or coerces a value out of a bag.
"""

from nuspace.web.refs.apps.interactions import ship
from nuspace.web.refs.apps.interactions.app import AppOps


__all__ = ["AppOps", "ship"]
