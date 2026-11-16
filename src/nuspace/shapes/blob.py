"""The space's blobs: one store of large bytes every run binds, and where the web device serves it.

Anything too big or too opaque for the kv stores: an image, a video, a
model's weights, a dataset. A cell keeps bytes in :data:`Blobs` and hands
out :data:`blobs`' urls::

    import nuspace

    bid = nuspace.Blobs.put_stream(drop.open(), mime="image/png", name="cat.png")
    pic.set_src(nuspace.blobs.url(bid))

Both are plain nustd values (``nustd.blob.StoreRef``,
``nustd.blob.http.BlobMount``), so their terms are nustd's. The store is
bound once per process, host and every worker, like the kv stores; the web
device serves it under ``/blobs``. Which backend it gets is the host's
(:mod:`nuspace.host.blobs`).

Workers import this module: nothing here may pull in a server.
"""

from __future__ import annotations

import nustd.blob
from nustd.blob.http import BlobMount


__all__ = ["Blobs", "blobs"]


#: The space's blob store. Bound in every process of an open.
Blobs = nustd.blob.StoreRef("blobs")

#: Where the web device serves :data:`Blobs`: ``blobs.url(id)`` for a leaf's
#: ``src``, ``blobs.url(id, download=True)`` for a download link.
blobs = BlobMount("/blobs")
