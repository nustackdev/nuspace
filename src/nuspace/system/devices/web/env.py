"""The session env (D17): a run drawing on one browser connection.

Registered as :data:`SESSION_ENV`, a run asks for it with
``ops.env("session", sid)``. The kernel resolves it in the host:

- **wrap**: opens :func:`proxied_session` on the connection around the
  run, and erases the cell's own ui node first, so what its last run
  drew goes before this one draws.
- **rewrite**: :class:`CellRoot`, landing the program's bare ui refs under
  the cell's node on the viewer.

Both are classes, not closures, so the built body and the rewrite pickle.
Everything here is safe for a worker to import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.ops import Here
from nuspace.system.devices.web.session import proxied_session
from nuspace.system.devices.web.shell import Shell
from nuspace.system.devices.web.utils import CellRoot, cell_ui
from nuspace.system.kernel import Env, EnvFactory


if TYPE_CHECKING:
    import nu


__all__ = ["SESSION_ENV", "SessionWrap", "session_env"]


#: The name the session env factory is registered under.
SESSION_ENV = "session"


class SessionWrap:
    """``body -> body``: the run inside connection ``sid``, its cell's ui cleared.

    Args:
        address: Where the host serves its connections.
        sid: The connection id.
    """

    __slots__ = ("address", "sid")

    def __init__(self, address: str, sid: str) -> None:
        self.address = address
        self.sid = sid

    def __call__(self, body: nu.Nu) -> nu.Nu:
        """``body``, drawing on the connection."""
        erase = cell_ui(Shell.viewer, Here.cell).erase()
        return proxied_session(self.address, self.sid, erase >> body)


def session_env(address: str) -> EnvFactory:
    """The session env factory for a host serving connections at ``address``.

    Returns:
        ``factory(sid) -> Env``, to register under :data:`SESSION_ENV`.
    """

    def factory(sid: str) -> Env:
        return Env(
            wrap=SessionWrap(address, sid),
            rewrite=CellRoot(Shell.viewer, Here.cell),
            label=f"{SESSION_ENV}:{sid}",
        )

    return factory
