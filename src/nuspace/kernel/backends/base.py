"""The backend contract: what every backend is, and how it says when it wants a worker.

A backend runs cells on workers. Each is a fabric, one instance per name,
bound on the host's context at open under :class:`Backend` tagged with its
name (:func:`~nuspace.kernel.backends.provided`). The kernel reaches one
only through :mod:`.interactions`, by the name on the plane run's record,
and never asks what kind it holds.

The kernel owns the worker records. It mints a worker's id
(``nuspace.worker.add``), the backend brings a worker up under that id and
hands back its handle, and every later call names the worker by that id::

    placement                    when the kernel wants a worker
    alaunch(worker) -> handle    bring one up under the minted id
    arun(worker, cell_run, body) run a cell run's body on it, to its end
    astop(worker)                let it go: polite first, forced past a grace
    akill(worker)                tear it down now
    areap(handle)                a leftover of an earlier open, by its handle

``placement`` is :data:`PER_PLANE_RUN` (one worker for the whole plane
run, taken before its first cell run) or :data:`PER_CELL_RUN` (one worker
per cell run, let go when it ends). A handle is a dict only its backend
reads: a process backend keeps pid and pgid there, a container backend a
container id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nu.lang import is_null


if TYPE_CHECKING:
    import nu


__all__ = [
    "PER_CELL_RUN",
    "PER_PLANE_RUN",
    "PLACEMENTS",
    "Backend",
    "UnknownBackendError",
    "require_backend",
]


#: One worker for the whole plane run, taken before its first cell run. Its
#: cell runs share it, and the plane run's end lets it go.
PER_PLANE_RUN = "plane_run"

#: One worker per cell run, taken when the cell run starts and let go when it ends.
PER_CELL_RUN = "cell_run"

#: Every placement a backend may declare.
PLACEMENTS = (PER_PLANE_RUN, PER_CELL_RUN)


class UnknownBackendError(LookupError):
    """A plane run names a backend nobody registered, or names none."""


class Backend:
    """What runs cells on workers. Subclass it, register the subclass by name at open.

    Every method is async and runs in the host. Worker ids are the kernel's:
    each method takes the id the kernel minted, so the records around the
    calls stay generic. A backend's own books (which process is which
    worker) are its own; the kernel keeps none of them.

    Attributes:
        placement: When the kernel wants a worker, one of :data:`PLACEMENTS`.
    """

    placement: ClassVar[str] = PER_CELL_RUN

    async def alaunch(self, worker: str) -> dict[str, object]:
        """Bring a worker up under ``worker``, the id the kernel minted. Its handle.

        Raises:
            Exception: It could not come up. The kernel ends the worker
                failed, and what wanted it with it.
        """
        raise NotImplementedError

    async def arun(self, worker: str, cell_run: str, body: nu.Nu) -> str:
        """Run a cell run's body on ``worker``, and return once it has ended.

        ``""`` when the body ran to its end, which it records itself. Why,
        when the worker died under it by itself: the kernel ends the cell run
        and the worker failed with that. A worker the backend let go on
        purpose is not a loss: whoever let it go ends what ran there.

        Cancelled, the body is cancelled where it runs.
        """
        raise NotImplementedError

    async def astop(self, worker: str) -> None:
        """Let ``worker`` go: polite first, forced past the backend's grace. Idempotent.

        A worker the backend does not know, or let go already, is a no-op.
        """
        raise NotImplementedError

    async def akill(self, worker: str) -> None:
        """Tear ``worker`` down now, nothing polite. Idempotent, as :meth:`astop`."""
        raise NotImplementedError

    async def areap(self, handle: dict[str, object]) -> None:
        """Tear down a worker an earlier open left, known only by its handle.

        Not called yet: reap marks leftovers killed and relies on the
        backend's own guard (mp_pool's parent watch kills a worker whose
        host died). Kill by handle comes in only if leftovers show up. The
        default does nothing.
        """
        del handle


def require_backend(value: object) -> Backend:
    """A :class:`~.interactions.BackendRef`'s value as a backend, or why there is none.

    Raises:
        UnknownBackendError: No backend is bound under the name, or none is named.
    """
    if isinstance(value, Backend):
        return value
    name = getattr(value, "name", value)
    if is_null(name) or name in ("", None):
        msg = "The plane names no backend: a plane that runs names one, eg mp or async"
        raise UnknownBackendError(msg)
    msg = f"No backend registered as {name!r}"
    raise UnknownBackendError(msg)
