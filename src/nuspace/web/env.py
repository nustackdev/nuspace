"""The session env: a run drawing on one browser tab.

Registered as :data:`SESSION_ENV`, nav asks for it on every pane's plane
run, ``envs=[["session", sid]]``. The kernel resolves it in the host:

- **wrap**: opens :func:`piped_session` on the tab around each cell run,
  with the tab's view of the upload area, and erases the cell's own ui node
  first, so what its last run drew goes before this one draws.
- **rewrite**: :class:`CellRoot`, landing the program's bare ui refs under
  the cell's node on the viewer.

Both are classes, not closures, so the built body and the rewrite pickle.
Everything here is safe for a worker to import.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.kernel.envs import Env, EnvFactory
from nuspace.places import Here

from .interactions import SESSION_ENV
from .session import piped_session
from .shell import Shell
from .utils import CellRoot, cell_ui


if TYPE_CHECKING:
    import nu


__all__ = ["SESSION_ENV", "SessionWrap", "session_env"]


class SessionWrap:
    """``body -> body``: the run inside tab ``sid``, its cell's ui cleared.

    Args:
        address: Where the host serves its connections.
        sid: The tab id.
        uploads: The upload area's root, where the tab's posted files land.
            None binds no upload view.
    """

    __slots__ = ("address", "sid", "uploads")

    def __init__(self, address: str, sid: str, uploads: str | None = None) -> None:
        self.address = address
        self.sid = sid
        self.uploads = uploads

    def __call__(self, body: nu.Nu) -> nu.Nu:
        """``body``, drawing on the tab."""
        erase = cell_ui(Shell.viewer, Here.cell).erase()
        return piped_session(self.address, self.sid, erase >> body, uploads=self.uploads)


def session_env(address: str, uploads: str | None = None) -> EnvFactory:
    """The session env factory for a host serving tabs at ``address``.

    Args:
        address: Where the host serves its connections.
        uploads: The upload area's root. None binds no upload view.

    Returns:
        ``factory(sid) -> Env``, to register under :data:`SESSION_ENV`.
    """

    def factory(sid: str) -> Env:
        return Env(
            wrap=SessionWrap(address, sid, uploads),
            rewrite=CellRoot(Shell.viewer, Here.cell),
            label=f"{SESSION_ENV}:{sid}",
        )

    return factory
