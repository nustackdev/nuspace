"""local.open: a space's stores without a driver, around a body of ops.

What a script or an agent uses to read and change a space, running or
not. It needs no infra, no kernel and no device, only a space initialized
(``local.init``). It binds every store, Space, State, Web and Conn, so web
ops such as desk edits work through it.

``open`` makes nothing, resets nothing, seeds nothing and takes no lock.
Like every entry point it binds local's mount of the data dir, so the
checks read ``meta.json`` through it.
With infra up it publishes to infra's notification server, so a write
lands in the stores and the kernel and web hear it. With none up nobody
listens: it binds the same files publishing nothing, and starts no
server. A plane run asked for through it is started by the live kernel,
or left pending for the next kernel to start.

Like every entry point it yields nothing: what a body wants to keep it
writes into a ref the caller holds (``into=``, ``nu.let``), as in a cell.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu

from ..blocks.meta import data_dir, resolve_root
from ..blocks.notifier import Answers
from . import binding
from .disk import entered, found
from .opening import ROOTS


if TYPE_CHECKING:
    import os

    from nu.context.fabric import Provide


__all__ = ["open"]


def open(
    path: str | os.PathLike[str],
    *,
    body: nu.Nu,
    blobs: Provide | None = None,
) -> nu.Nu:
    """The space at ``path``'s stores bound around ``body``, a body of ops. No driver runs.

    Ops run as in a cell: brackets, ``nuspace.atomic``, named targets, no
    ``Here``. Takes no lock: beside a live kernel and web, or with nothing
    up. Publishes to infra's notification server when it answers as
    this starts, else publishes nothing (nobody listens). Yields nothing:
    the body writes what it keeps into a ref the caller holds.

    Args:
        path: The space's root. It must be a local space, initialized.
        body: What runs with the stores bound.
        blobs: The blob store, as ``local.kernel``. None is local's files.

    Raises:
        Missing: No space at ``path`` (at run).
        Refused: A space not initialized, another assembly's, or of an
            older store format (at run).
    """
    root, _ = resolve_root(path)
    data = str(data_dir(root))
    blobs = binding.blobs(data) if blobs is None else blobs
    published = nu.With(binding.stores(data, ROOTS), blobs, body=body)
    quiet = nu.With(binding.quiet(data, ROOTS), blobs, body=body)
    chosen = nu.IfDo(Answers(binding.valkey_dir(data)), published, quiet)
    return found(root) >> entered(root, chosen)
