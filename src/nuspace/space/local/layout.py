"""Local's layout: every concrete name the local assembly gives a space on disk. Nowhere else names them.

Inside the data dir (``.nuspace/``, with ``meta.json``, both the blocks')::

    store/space.db             Space    channel nuspace.space
    store/state.db             State    channel nuspace.state
    store/blobs/               Blobs, plain files
    kernel/kernel.lock         one kernel per space
    kernel/kernel.log          what the kernel says
    devices/web/web.lock       one web per space
    devices/web/web.log        what web says
    devices/web/web_state.db   Web      channel nuspace.web
    devices/web/conn.db        Conn     channel nuspace.conn
    devices/web/uploads/       files tabs posted, wiped when web starts
    devices/web/session.addr   where workers reach web's tab sessions
    infra/infra.lock           one infra per space
    infra/infra.log            what infra says
    infra/valkey/              the notification server's dir

Every name is relative to the data dir, which local's entry points bind
as one ``nustd.fs`` mount under a tag of local's own (:data:`DATA`): the
files local reads and writes there go through it, and every absolute path
a store, a log or the notification server takes is ``DATA.where(name)``,
asked when the term runs. Around it sits a read only mount of the space's
root (:data:`ROOT`), which the checks before the data dir's mount look
through, and whose ``where()`` is the root itself, absolute. A space made before ``meta.json``
holds :data:`MADE_BEFORE` and no meta: local adopts it. A space of the
store format before that holds one of :data:`OLDER`: refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import nustd.fs
from nuspace.shapes import Space, State
from nuspace.web.shapes import Conn, Web

from ..blocks.meta import META_FILE


if TYPE_CHECKING:
    import nu


__all__ = [
    "ASSEMBLY",
    "BLOBS_DIR",
    "DATA",
    "DIRS",
    "INFRA_LOCK",
    "INFRA_LOG",
    "KERNEL_LOCK",
    "KERNEL_LOG",
    "MADE_BEFORE",
    "META",
    "MOUNT",
    "OLDER",
    "ROOT",
    "ROOT_MOUNT",
    "SESSION_ADDR",
    "STORES",
    "UPLOADS_DIR",
    "VALKEY_DIR",
    "WEB_LOCK",
    "WEB_LOG",
    "Placed",
]


#: The name ``meta.json`` gives this assembly.
ASSEMBLY = "local"

#: The tag local binds its mount of the data dir under, so no other mount is mistaken for it.
MOUNT = "nuspace.local"

#: The data dir, as local's mount: ``DATA / KERNEL_LOCK`` is the kernel's lock file on it.
DATA = nustd.fs.FsRef(MOUNT)

#: ``meta.json`` on local's mount.
META = DATA / META_FILE

#: The tag local binds its read only mount of the space's root under.
ROOT_MOUNT = "nuspace.local.root"

#: The space's root, as local's read only mount: ``ROOT.where()`` is the root, absolute.
ROOT = nustd.fs.FsRef(ROOT_MOUNT)


@dataclass(frozen=True)
class Placed:
    """Where local keeps one store.

    Attributes:
        file: Its SQLite file.
        channel: Its notify channel prefix, one per store, so two stores
            never wake each other's subscribers, even on equal keys.
    """

    file: str
    channel: str


#: Each store by its root shape.
STORES: dict[type[nu.Shape], Placed] = {
    Space: Placed("store/space.db", "nuspace.space"),
    State: Placed("store/state.db", "nuspace.state"),
    Web: Placed("devices/web/web_state.db", "nuspace.web"),
    Conn: Placed("devices/web/conn.db", "nuspace.conn"),
}

#: The blob store's dir, plain files, beside the kv stores.
BLOBS_DIR = "store/blobs"

#: Infra's lock and log: what runs the space, the notification server.
INFRA_LOCK = "infra/infra.lock"
INFRA_LOG = "infra/infra.log"

#: The kernel's lock and log.
KERNEL_LOCK = "kernel/kernel.lock"
KERNEL_LOG = "kernel/kernel.log"

#: Web's lock and log.
WEB_LOCK = "devices/web/web.lock"
WEB_LOG = "devices/web/web.log"

#: Files tabs posted, read by workers by path. Wiped when web starts.
UPLOADS_DIR = "devices/web/uploads"

#: Where web writes the address its tab sessions answer at, for the kernel's workers.
SESSION_ADDR = "devices/web/session.addr"

#: The notification server's dir: ``infra/`` holds what runs the space, not what it holds.
VALKEY_DIR = "infra/valkey"

#: The dirs local makes in the data dir before anything opens.
DIRS = ("store", "kernel", "devices/web", "infra")

#: What a space made before ``meta.json`` holds: its Space store.
MADE_BEFORE = STORES[Space].file

#: What a nuspace of an older store format kept, in the data dir or loose
#: in the root: its stores, or a RocksDB store's ``CURRENT``. Refused, no converter.
OLDER = ("kernel.sqlite", "state.sqlite", "CURRENT")
