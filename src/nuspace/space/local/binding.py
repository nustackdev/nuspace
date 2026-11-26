"""Local's bindings: each store on its SQLite file, notified through the space's one Valkey, blobs as files.

What every process on a local space binds, the same way: the kernel, web,
an ``open``, and each worker (the pool gets the same term pickled). The
stores go through the navigators block, one stack per root, so the
drivers only ever see the root shapes. Names come from :mod:`.layout`.

Every path is a path on local's mount of the data dir, asked when the term
runs (``DATA.where(name)``), so a binding needs that mount bound around it:
an entry point's, or a worker's own (:mod:`.drivers`).

Infra owns the Valkey server (:func:`served`); the kernel, web and every
worker publish to it. With no infra up nobody listens, so ``open`` and
``init`` bind :func:`quiet` stores then: the same files, nothing published.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import nu
import nustd.blob
import nustd.kv
import nustd.valkey
from nuspace.shapes import Blobs

from ..blocks import navigators
from ..blocks import notifier as _notifier
from .layout import BLOBS_DIR, DATA, STORES, VALKEY_DIR


if TYPE_CHECKING:
    from collections.abc import Iterable

    from nu.context.fabric import Provide


__all__ = ["blob_backend", "blobs", "quiet", "served", "stores", "valkey_dir", "valkey_url"]


def valkey_dir() -> nu.Nu:
    """The notification server's dir, absolute, on local's mount of the data dir. A query."""
    return DATA.where(VALKEY_DIR)


def valkey_url() -> nu.Nu:
    """The notification server's url, a unix socket derived from its dir. A query.

    ``nustd.valkey.url_for`` hashes the dir, a plain function over a
    value: it runs on every evaluation, the dir read from the mount first.
    """
    return nu.Literal(factory=nustd.valkey.url_for, data_dir=valkey_dir())


def served() -> Provide:
    """The space's notification server, started and owned for the body: infra's."""
    return _notifier.served(valkey_dir())


def stores(roots: Iterable[type[nu.Shape]]) -> nu.With:
    """Each of ``roots`` bound to its SQLite file on the data dir, notified on its own channel.

    Needs the server of :func:`served` up: its publishers connect at setup.

    Args:
        roots: The stores' root shapes, eg ``(Space, State)``.
    """
    url = valkey_url()
    return nu.With(
        *(
            navigators.navigator(
                root,
                functools.partial(
                    nustd.kv.sqlite_navigator_redis,
                    DATA.where(STORES[root].file),
                    redis_url=url,
                    channel_prefix=STORES[root].channel,
                ),
            )
            for root in roots
        )
    )


def quiet(roots: Iterable[type[nu.Shape]]) -> nu.With:
    """Each of ``roots`` bound to its SQLite file on the data dir, publishing nothing.

    For a process on a space with no infra up, so no server to publish to
    and nobody to hear it. A kernel starting later reads the stores as
    they are, so nothing is missed.

    Args:
        roots: The stores' root shapes.
    """
    return nu.With(
        *(
            navigators.navigator(
                root,
                functools.partial(nustd.kv.sqlite_navigator, DATA.where(STORES[root].file)),
            )
            for root in roots
        )
    )


def blobs() -> Provide:
    """The blob store: plain files in the data dir's ``store/blobs``. Any size the disk holds.

    ``nustd.blob.files`` fixes its dir when the tree is built, so this is
    its ``Provide`` with the dir a query on the mount instead.

    An assembly of one's own picks any other ``nustd.blob`` spec, eg
    ``nustd.blob.lmdb(nuspace.Blobs, path)`` for many small blobs.
    """
    options = nu.Dict.of(root=DATA.where(BLOBS_DIR))
    return nu.Provide(
        nustd.blob.BlobFabric,
        kwargs={"backend": nustd.blob.FilesBackend, "options": options},
        tag=Blobs.name,
    )


def blob_backend() -> nu.Nu:
    """The backend over :func:`blobs`' dir, not open yet, made where it runs: what web's blob routes serve.

    The routes answer outside any tree, so they take a plain backend of
    their own rather than the bound store: the same dir is the same store.
    """
    return nu.Literal(factory=nustd.blob.FilesBackend, root=DATA.where(BLOBS_DIR))
